import { ClaimSentence } from '../types.ts';

/**
 * Assigns stable sequential numbers (1, 2, 3...) to chunks across an answer.
 * If multiple sentences reference the same chunk, they share the same number.
 */
export function numberChunks(sentences: ClaimSentence[]): Map<string, number> {
  const map = new Map<string, number>();
  let nextNumber = 1;

  for (const sentence of sentences) {
    for (const chunkId of sentence.citations) {
      if (!map.has(chunkId)) {
        map.set(chunkId, nextNumber++);
      }
    }
  }

  return map;
}
