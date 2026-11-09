import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ClaimSentence, SourceChunk } from '../../types.ts';
import { useCitationStore } from '../../stores/citationStore.ts';
import { useUIStore } from '../../stores/uiStore.ts';

interface ClaimSentenceViewProps {
  sentence: ClaimSentence;
  chunks: Record<string, SourceChunk>;
  chunkNumberMap: Map<string, number>;
  isStreaming?: boolean;
}

export const ClaimSentenceView: React.FC<ClaimSentenceViewProps> = ({
  sentence,
  chunks,
  chunkNumberMap,
  isStreaming = false,
}) => {
  const { activeChunk, selectCitation } = useCitationStore();
  const { setInspectorOpen } = useUIStore();

  // High-performance 60 FPS streaming mode: zero markdown AST thrashing, inline blinking cursor
  if (isStreaming) {
    return (
      <div className="text-ink mb-2 whitespace-pre-wrap leading-relaxed font-sans text-base">
        {sentence.text}
        <span
          className="inline-block w-1.5 h-4 ml-1 bg-mark align-middle rounded-xs"
          style={{ animation: 'kx-glow 0.8s ease-in-out infinite' }}
        />
      </div>
    );
  }

  const markdownComponents = {
    p: ({ children }: { children?: React.ReactNode }) => <div className="mb-2 leading-relaxed">{children}</div>,
    a: ({ href, children }: { href?: string; children?: React.ReactNode }) => {
      if (href && (href.startsWith('http://') || href.startsWith('https://'))) {
        return (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-mark underline hover:opacity-80 transition-opacity"
          >
            {children}
          </a>
        );
      }
      return <span>{children}</span>;
    },
    code: ({ children }: { children?: React.ReactNode }) => (
      <code className="px-1.5 py-0.5 bg-elevated border border-line font-mono text-xs text-ink rounded-input">
        {children}
      </code>
    ),
    strong: ({ children }: { children?: React.ReactNode }) => (
      <strong className="font-semibold text-ink">{children}</strong>
    ),
    em: ({ children }: { children?: React.ReactNode }) => (
      <em className="italic text-ink">{children}</em>
    ),
    // Rich Table Rendering
    table: ({ children }: { children?: React.ReactNode }) => (
      <div className="my-4 overflow-x-auto rounded-input border border-line bg-surface shadow-sm">
        <table className="w-full text-left text-sm border-collapse font-sans">
          {children}
        </table>
      </div>
    ),
    thead: ({ children }: { children?: React.ReactNode }) => (
      <thead className="bg-elevated/70 border-b border-line text-xs font-mono uppercase text-secondary">
        {children}
      </thead>
    ),
    tbody: ({ children }: { children?: React.ReactNode }) => (
      <tbody className="divide-y divide-line/60 font-sans text-ink">
        {children}
      </tbody>
    ),
    tr: ({ children }: { children?: React.ReactNode }) => (
      <tr className="hover:bg-elevated/30 transition-colors">
        {children}
      </tr>
    ),
    th: ({ children }: { children?: React.ReactNode }) => (
      <th className="px-3.5 py-2.5 font-medium tracking-wider">
        {children}
      </th>
    ),
    td: ({ children }: { children?: React.ReactNode }) => (
      <td className="px-3.5 py-2.5 whitespace-normal leading-normal">
        {children}
      </td>
    ),
    ul: ({ children }: { children?: React.ReactNode }) => (
      <ul className="list-disc list-inside my-2 space-y-1 text-ink pl-1">
        {children}
      </ul>
    ),
    ol: ({ children }: { children?: React.ReactNode }) => (
      <ol className="list-decimal list-inside my-2 space-y-1 text-ink pl-1">
        {children}
      </ol>
    ),
    li: ({ children }: { children?: React.ReactNode }) => (
      <li className="leading-relaxed">{children}</li>
    ),
    blockquote: ({ children }: { children?: React.ReactNode }) => (
      <blockquote className="border-l-2 border-mark pl-3 my-2 italic text-secondary bg-elevated/20 py-1 rounded-r-input">
        {children}
      </blockquote>
    ),
  };

  return (
    <div className="text-ink mb-2">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {sentence.text}
      </ReactMarkdown>

      {sentence.citations && sentence.citations.length > 0 && (
        <span className="inline-flex items-center gap-1 ml-1 mt-0.5 align-middle select-none">
          {sentence.citations.map((chunkId) => {
            const chunk = chunks[chunkId];
            if (!chunk) return null;

            const num = chunkNumberMap.get(chunkId) ?? 1;
            // Compare by unique chunk ID, not by display number.
            // This prevents citation [5] in one answer highlighting [5] in another.
            const isActive = activeChunk?.id === chunkId;

            return (
              <button
                key={chunkId}
                type="button"
                aria-label={`Source ${num}: ${chunk.filename}, page ${chunk.page}`}
                aria-pressed={isActive}
                onClick={() => {
                  selectCitation(chunk, sentence.text, num);
                  setInspectorOpen(true);
                }}
                className={`
                  inline-flex items-center justify-center
                  px-1.5 h-4 min-w-4 text-xs font-mono
                  rounded-chip border transition-all cursor-pointer
                  ${isActive
                    ? 'bg-mark border-mark text-bg font-semibold scale-110 shadow-sm'
                    : 'bg-elevated/70 border-line text-secondary hover:border-mark hover:text-mark'
                  }
                `}
              >
                {num}
              </button>
            );
          })}
        </span>
      )}
    </div>
  );
};

