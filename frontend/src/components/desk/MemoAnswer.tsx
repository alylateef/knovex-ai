import React from 'react';
import { AnswerResponse } from '../../types.ts';
import { numberChunks } from '../../lib/numberChunks.ts';
import { ClaimSentenceView } from './ClaimSentenceView.tsx';
import { AbstainedBlock } from './AbstainedBlock.tsx';
import { TimingBar } from './TimingBar.tsx';

interface MemoAnswerProps {
  question: string;
  answer?: AnswerResponse;
  loading?: boolean;
  error?: string;
}

/** Three animated dots — thinking indicator */
const ThinkingDots: React.FC = () => (
  <span className="inline-flex items-center space-x-1 ml-1" aria-label="Searching documents">
    <span className="kx-dot" />
    <span className="kx-dot" />
    <span className="kx-dot" />
  </span>
);

export const MemoAnswer: React.FC<MemoAnswerProps> = ({
  question,
  answer,
  loading,
  error,
}) => {
  const chunkNumberMap = answer ? numberChunks(answer.sentences) : new Map<string, number>();

  return (
    <article className="kx-fade-in max-w-prose my-6">

      {/* Question bubble — flush left, distinct treatment */}
      <div className="mb-4 flex items-start space-x-3">
        {/* Avatar monogram */}
        <div
          aria-hidden="true"
          className="shrink-0 w-6 h-6 rounded-chip bg-elevated border border-line text-secondary flex items-center justify-center text-xs font-mono font-medium select-none mt-0.5"
        >
          Q
        </div>
        <h2 className="font-sans font-medium text-base text-ink leading-snug pt-0.5">
          {question}
        </h2>
      </div>

      {/* Answer card — left chrome accent */}
      <div className="relative pl-4 mt-2">
        {/* Left chrome line — mark accent */}
        <div
          aria-hidden="true"
          className="absolute left-0 top-1 bottom-1 w-0.5 bg-mark rounded-chip opacity-80"
        />

        {/* Loading state — thinking dots */}
        {loading && (
          <div className="flex items-center space-x-2 py-3 text-sm font-mono text-secondary">
            <span>Retrieving and verifying sources</span>
            <ThinkingDots />
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="py-2.5 px-3 border-l-2 border-danger text-danger text-sm font-sans bg-elevated/40 rounded-r-input">
            {error}
          </div>
        )}

        {/* Answer body */}
        {answer && (
          <div className="pr-1">
            {answer.abstained ? (
              <AbstainedBlock reason={answer.reason} />
            ) : (
              <div className="font-sans text-base leading-relaxed text-ink">
                {answer.sentences.map((sent, idx) => (
                  <ClaimSentenceView
                    key={idx}
                    sentence={sent}
                    chunks={answer.chunks}
                    chunkNumberMap={chunkNumberMap}
                  />
                ))}
              </div>
            )}
            <TimingBar timings={answer.timings} />
          </div>
        )}
      </div>
    </article>
  );
};
