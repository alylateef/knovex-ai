import { AnswerResponse, SourceChunk, ClaimSentence, Timings } from '../types.ts';

export function parseAnswer(raw: unknown): AnswerResponse {
  if (typeof raw !== 'object' || raw === null) {
    throw new Error('Invalid answer response: expected an object.');
  }

  const obj = raw as Record<string, unknown>;

  const abstained = Boolean(obj.abstained);
  const reason = typeof obj.reason === 'string' ? obj.reason : undefined;

  // Chunks map
  const rawChunks = (typeof obj.chunks === 'object' && obj.chunks !== null ? obj.chunks : {}) as Record<string, unknown>;
  const chunks: Record<string, SourceChunk> = {};

  for (const [id, c] of Object.entries(rawChunks)) {
    if (typeof c === 'object' && c !== null) {
      const cObj = c as Record<string, unknown>;
      const scoresObj = (typeof cObj.scores === 'object' && cObj.scores !== null ? cObj.scores : {}) as Record<string, unknown>;

      chunks[id] = {
        id,
        doc_id: String(cObj.doc_id ?? ''),
        filename: String(cObj.filename ?? 'unknown'),
        page: typeof cObj.page === 'number' ? cObj.page : 1,
        char_count: typeof cObj.char_count === 'number' ? cObj.char_count : String(cObj.text ?? '').length,
        text: String(cObj.text ?? ''),
        indexed_at: typeof cObj.indexed_at === 'string' ? cObj.indexed_at : undefined,
        scores: {
          dense: typeof scoresObj.dense === 'number' ? scoresObj.dense : undefined,
          sparse: typeof scoresObj.sparse === 'number' ? scoresObj.sparse : undefined,
          rerank: typeof scoresObj.rerank === 'number' ? scoresObj.rerank : undefined,
        },
      };
    }
  }

  // Sentences
  const rawSentences = Array.isArray(obj.sentences) ? obj.sentences : [];
  const sentences: ClaimSentence[] = [];

  for (const s of rawSentences) {
    if (typeof s === 'object' && s !== null) {
      const sObj = s as Record<string, unknown>;
      const text = String(sObj.text ?? '').trim();
      if (!text) continue;

      const rawCitations = Array.isArray(sObj.citations) ? sObj.citations : [];
      // Drop citations that point to a missing chunk
      const validCitations: string[] = [];
      for (const cit of rawCitations) {
        const citId = String(cit);
        if (chunks[citId]) {
          validCitations.push(citId);
        }
      }

      sentences.push({
        text,
        citations: validCitations,
      });
    }
  }

  // Timings
  const rawTimings = (typeof obj.timings === 'object' && obj.timings !== null ? obj.timings : {}) as Record<string, unknown>;
  const timings: Timings = {
    retrieval_ms: typeof rawTimings.retrieval_ms === 'number' ? rawTimings.retrieval_ms : 0,
    rerank_ms: typeof rawTimings.rerank_ms === 'number' ? rawTimings.rerank_ms : 0,
    llm_ms: typeof rawTimings.llm_ms === 'number' ? rawTimings.llm_ms : 0,
  };

  return {
    sentences,
    chunks,
    timings,
    abstained,
    reason,
  };
}
