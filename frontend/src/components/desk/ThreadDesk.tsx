import React, { useState, useRef, useEffect } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore.ts';
import { useThreadsStore } from '../../stores/threadsStore.ts';
import { useUIStore } from '../../stores/uiStore.ts';
import { SegmentedControl } from './SegmentedControl.tsx';
import { MemoAnswer } from './MemoAnswer.tsx';
import { RAGMode, TopK } from '../../types.ts';

/* ------------------------------------------------------------------ */
/* Empty state — shown when thread has no messages yet                  */
/* ------------------------------------------------------------------ */
const EmptyThreadState: React.FC = () => (
  <div className="h-full flex flex-col items-center justify-center text-center px-8 select-none">
    <div className="mb-5">
      <img
        src="/logo.png"
        alt="Knovex AI"
        style={{ width: '42px', height: '42px' }}
        className="rounded-chip object-cover mx-auto opacity-85"
      />
    </div>
    <h3 className="font-sans font-bold text-xl text-ink mb-2">
      Knovex Document Intelligence
    </h3>
    <p className="font-sans text-sm text-secondary max-w-sm leading-relaxed">
      Ask a question grounded directly in your uploaded documents.
      Every claim is traceable to a source passage.
    </p>
    <p className="font-mono text-xs text-muted mt-4">
      Hybrid Retrieval · CrossEncoder Reranker · Grounded Verification
    </p>
  </div>
);

/* ------------------------------------------------------------------ */
/* History loading skeleton                                             */
/* ------------------------------------------------------------------ */
const HistorySkeleton: React.FC = () => (
  <div className="space-y-6 px-4 md:px-8 py-6">
    {[1, 2].map((i) => (
      <div key={i} className="space-y-2 animate-pulse">
        <div className="h-4 bg-panel w-1/3" />
        <div className="h-3 bg-panel w-full" />
        <div className="h-3 bg-panel w-5/6" />
        <div className="h-3 bg-panel w-4/6" />
      </div>
    ))}
  </div>
);

/* ------------------------------------------------------------------ */
/* Main ThreadDesk                                                       */
/* ------------------------------------------------------------------ */
export const ThreadDesk: React.FC = () => {
  const [input, setInput] = useState('');
  const [isTuneOpen, setIsTuneOpen] = useState(false);

  const { isSubmitting, ask } = useChatStore();
  const { topK, setTopK, mode, setMode } = useUIStore();
  const { activeThreadId, messagesByThread, loadingHistory } = useThreadsStore();

  const scrollRef = useRef<HTMLDivElement>(null);
  const tuneRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const messages = activeThreadId
    ? (messagesByThread[activeThreadId] ?? [])
    : (messagesByThread['__pending__'] ?? []);

  const isLoadingHistory = activeThreadId
    ? (loadingHistory[activeThreadId] ?? false)
    : false;

  const passageOptions = [
    { value: 3 as TopK, label: '3' },
    { value: 5 as TopK, label: '5' },
    { value: 8 as TopK, label: '8' },
  ];

  const modeOptions = [
    { value: 'dense' as RAGMode, label: 'Meaning' },
    { value: 'hybrid' as RAGMode, label: 'Hybrid' },
    { value: 'rerank' as RAGMode, label: 'Hybrid + Rerank' },
  ];

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Re-focus input after thread switch
  useEffect(() => {
    if (!isLoadingHistory) {
      inputRef.current?.focus();
    }
  }, [activeThreadId, isLoadingHistory]);

  // Close tune popover on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (tuneRef.current && !tuneRef.current.contains(e.target as Node)) {
        setIsTuneOpen(false);
      }
    };
    if (isTuneOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isTuneOpen]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || isSubmitting) return;
    setInput('');
    setIsTuneOpen(false);
    void ask(q, topK, mode);
  };

  return (
    <main className="flex-1 flex flex-col h-full bg-bg overflow-hidden relative">

      {/* Scrollable Thread Memos */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6">

        {isLoadingHistory ? (
          <HistorySkeleton />
        ) : messages.length === 0 ? (
          <EmptyThreadState />
        ) : (
          messages.map((m) => (
            <MemoAnswer
              key={m.id}
              question={m.question}
              answer={m.answer}
              loading={m.loading}
              error={m.error}
            />
          ))
        )}

      </div>

      {/* Pinned Input Bar at Bottom */}
      <div className="p-4 border-t border-line bg-surface shrink-0 relative">
        <form onSubmit={handleSubmit} className="max-w-prose mx-auto flex items-center space-x-2 relative">

          <div className="relative flex-1 flex items-center">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isSubmitting}
              placeholder={
                isSubmitting
                  ? 'Searching your documents…'
                  : 'Ask a question about your documents…'
              }
              className="w-full pl-3 pr-8 py-2 bg-bg border border-line text-ink text-sm rounded-input focus:border-mark focus:outline-none placeholder:text-muted transition-colors"
            />

            {/* Subtle RAG tuning button */}
            <div className="absolute right-2" ref={tuneRef}>
              <button
                type="button"
                onClick={() => setIsTuneOpen(!isTuneOpen)}
                title="RAG Engine Parameters"
                aria-label="RAG Engine Parameters"
                className={`p-1 rounded-chip transition-colors ${
                  isTuneOpen
                    ? 'text-mark bg-mark-bg'
                    : 'text-secondary hover:text-ink hover:bg-elevated'
                }`}
              >
                <SlidersHorizontal size={14} strokeWidth={1.5} />
              </button>

              {/* Minimal Popover */}
              {isTuneOpen && (
                <div className="absolute right-0 bottom-8 mb-2 p-3.5 bg-surface border border-line rounded-input shadow-lg z-20 w-72 space-y-3">
                  <div className="flex items-center justify-between pb-1 border-b border-line">
                    <span className="text-xs font-mono uppercase tracking-wider text-secondary">
                      Engine Parameters
                    </span>
                    <span className="text-xs font-mono text-mark font-medium">
                      {mode}
                    </span>
                  </div>

                  <div>
                    <span className="block text-xs font-mono text-secondary mb-1">
                      Context Passages
                    </span>
                    <SegmentedControl
                      name="popover-passages"
                      label="Passages count"
                      value={topK}
                      onChange={setTopK}
                      options={passageOptions}
                    />
                  </div>

                  <div>
                    <span className="block text-xs font-mono text-secondary mb-1">
                      Retrieval Strategy
                    </span>
                    <SegmentedControl
                      name="popover-mode"
                      label="Search Mode"
                      value={mode}
                      onChange={setMode}
                      options={modeOptions}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !input.trim()}
            className="px-4 py-2 bg-mark hover:bg-mark-hover text-bg font-sans font-medium text-sm rounded-button transition-colors disabled:opacity-40 shrink-0"
          >
            {isSubmitting ? 'Searching…' : 'Ask'}
          </button>
        </form>
      </div>
    </main>
  );
};
