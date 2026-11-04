import React, { useEffect, useRef } from 'react';
import { X, Copy } from 'lucide-react';
import { useCitationStore } from '../../stores/citationStore.ts';
import { useUIStore } from '../../stores/uiStore.ts';
import { ScoreGauge } from './ScoreGauge.tsx';

export const Inspector: React.FC = () => {
  const { activeChunk, activeClaim, activeNumber, clearCitation } = useCitationStore();
  const { inspectorOpen, setInspectorOpen } = useUIStore();
  const inspectorRef = useRef<HTMLDivElement>(null);
  const copyBtnRef = useRef<HTMLButtonElement>(null);

  const close = () => {
    setInspectorOpen(false);
    clearCitation();
  };

  // Keyboard: Esc closes
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && inspectorOpen) close();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [inspectorOpen]);

  if (!inspectorOpen || !activeChunk) return null;

  const copyPassage = () => {
    navigator.clipboard.writeText(activeChunk.text).then(() => {
      if (copyBtnRef.current) {
        const original = copyBtnRef.current.textContent;
        copyBtnRef.current.textContent = 'Copied!';
        setTimeout(() => {
          if (copyBtnRef.current) copyBtnRef.current.textContent = original ?? 'Copy passage';
        }, 1200);
      }
    });
  };

  return (
    <>
      {/* Mobile backdrop */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Close Inspector"
        onClick={close}
        onKeyDown={(e) => { if (e.key === 'Escape') close(); }}
        className="fixed inset-0 bg-black/40 backdrop-blur-xs z-30 md:hidden transition-opacity cursor-pointer"
      />

      <aside
        ref={inspectorRef}
        role="dialog"
        aria-modal="true"
        aria-label="Citation Inspector"
        className="kx-slide-up fixed inset-x-0 bottom-0 max-h-[85vh] md:static md:w-source md:max-h-full shrink-0 border-t md:border-t-0 md:border-l border-line bg-surface flex flex-col overflow-y-auto z-40 shadow-2xl md:shadow-none rounded-t-2xl md:rounded-none"
      >
      {/* ── Header ── */}
      <div className="px-5 pt-5 pb-3 border-b border-line shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            {/* Citation number badge */}
            <span className="w-6 h-6 flex items-center justify-center rounded-chip bg-mark-bg border border-mark text-mark font-mono font-bold text-xs">
              {activeNumber ?? 1}
            </span>
            <span className="text-xs font-mono text-secondary uppercase tracking-wider font-medium">
              Source Inspector
            </span>
          </div>
          <button
            type="button"
            onClick={close}
            aria-label="Close Inspector"
            className="p-1 text-secondary hover:text-ink hover:bg-elevated transition-colors rounded-chip"
          >
            <X size={15} strokeWidth={1.5} />
          </button>
        </div>
      </div>

      {/* ── Body ── */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">

        {/* The Claim */}
        {activeClaim && (
          <div>
            <div className="text-xs font-mono text-secondary uppercase tracking-wider mb-2 font-medium">
              The Claim
            </div>
            <div className="relative p-3 bg-mark-bg border-l-2 border-mark text-sm font-sans text-ink leading-relaxed rounded-r-input">
              <span className="italic">"{activeClaim}"</span>
            </div>
          </div>
        )}

        {/* What the source says */}
        <div>
          <div className="text-xs font-mono text-secondary uppercase tracking-wider mb-2 font-medium">
            What the source says
          </div>
          <blockquote className="p-3.5 bg-bg border border-line text-sm font-serif text-ink leading-relaxed whitespace-pre-wrap rounded-input">
            {activeChunk.text}
          </blockquote>
        </div>

        {/* Metadata grid */}
        <div className="border-t border-line pt-4">
          <div className="text-xs font-mono text-secondary uppercase tracking-wider mb-2 font-medium">
            Metadata
          </div>
          <table className="w-full text-xs font-mono">
            <tbody className="space-y-1">
              <tr>
                <td className="text-secondary pr-3 py-0.5">File</td>
                <td className="text-ink truncate max-w-ellipsis text-right" title={activeChunk.filename}>
                  {activeChunk.filename}
                </td>
              </tr>
              <tr>
                <td className="text-secondary pr-3 py-0.5">Page</td>
                <td className="text-ink text-right">{activeChunk.page}</td>
              </tr>
              <tr>
                <td className="text-secondary pr-3 py-0.5">Characters</td>
                <td className="text-ink text-right">{activeChunk.char_count.toLocaleString()}</td>
              </tr>
              {activeChunk.indexed_at && (
                <tr>
                  <td className="text-secondary pr-3 py-0.5">Indexed</td>
                  <td className="text-ink text-right">
                    {new Date(activeChunk.indexed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Relevance gauges */}
        <div className="border-t border-line pt-4 space-y-3">
          <div className="text-xs font-mono text-secondary uppercase tracking-wider mb-2 font-medium">
            Relevance
          </div>
          <ScoreGauge label="Meaning (Dense)" value={activeChunk.scores.dense} />
          <ScoreGauge label="Keywords (Sparse)" value={activeChunk.scores.sparse} />
          <ScoreGauge label="Rerank Score" value={activeChunk.scores.rerank} />
        </div>

      </div>

      {/* ── Footer action ── */}
      <div className="px-5 pb-5 pt-3 border-t border-line shrink-0">
        <button
          ref={copyBtnRef}
          type="button"
          onClick={copyPassage}
          className="w-full py-2 px-3 bg-elevated hover:bg-elevated/75 border border-line text-ink text-xs font-mono flex items-center justify-center space-x-2 rounded-button transition-colors cursor-pointer"
        >
          <Copy size={13} strokeWidth={1.5} />
          <span>Copy passage</span>
        </button>
      </div>
    </aside>
  </>
  );
};
