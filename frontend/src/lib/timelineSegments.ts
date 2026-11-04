import { Timings } from '../types.ts';

export interface TimelineSegment {
  label: string;
  ms: number;
  pct: number;
}

export function timelineSegments(timings: Timings): TimelineSegment[] {
  const total = Math.max(1, timings.retrieval_ms + timings.rerank_ms + timings.llm_ms);

  return [
    {
      label: 'Retrieval',
      ms: timings.retrieval_ms,
      pct: (timings.retrieval_ms / total) * 100,
    },
    {
      label: 'Rerank',
      ms: timings.rerank_ms,
      pct: (timings.rerank_ms / total) * 100,
    },
    {
      label: 'Model',
      ms: timings.llm_ms,
      pct: (timings.llm_ms / total) * 100,
    },
  ];
}
