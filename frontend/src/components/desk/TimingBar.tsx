import React from 'react';
import { timelineSegments } from '../../lib/timelineSegments.ts';
import { Timings } from '../../types.ts';

interface TimingBarProps {
  timings: Timings;
}

export const TimingBar: React.FC<TimingBarProps> = ({ timings }) => {
  const segments = timelineSegments(timings);
  const total = timings.retrieval_ms + timings.rerank_ms + timings.llm_ms;

  // Don't render if all zeros (history messages without timing data)
  if (total === 0) return null;

  return (
    <div className="mt-5 pt-3 border-t border-line">
      {/* Segment bar */}
      <div className="w-full h-1 bg-elevated flex overflow-hidden rounded-chip mb-2">
        {segments.map((seg, idx) => {
          const style =
            idx === 0
              ? 'bg-mark opacity-40'
              : idx === 1
              ? 'bg-mark opacity-65'
              : 'bg-mark opacity-100';
          return (
            <div
              key={seg.label}
              style={{ width: `${seg.pct}%` }}
              className={`h-full transition-all ${style}`}
              title={`${seg.label}: ${seg.ms} ms`}
            />
          );
        })}
      </div>

      {/* Labels */}
      <div className="flex items-center space-x-3 text-xs font-mono text-secondary">
        <span className="flex items-center space-x-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-chip bg-mark opacity-40" />
          <span>Retrieval {timings.retrieval_ms} ms</span>
        </span>
        {timings.rerank_ms > 0 && (
          <span className="flex items-center space-x-1.5">
            <span className="inline-block w-1.5 h-1.5 rounded-chip bg-mark opacity-65" />
            <span>Rerank {timings.rerank_ms} ms</span>
          </span>
        )}
        <span className="flex items-center space-x-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-chip bg-mark opacity-100" />
          <span>Model {timings.llm_ms} ms</span>
        </span>
        <span className="ml-auto text-muted">
          {total < 1000 ? `${total} ms total` : `${(total / 1000).toFixed(1)} s total`}
        </span>
      </div>
    </div>
  );
};
