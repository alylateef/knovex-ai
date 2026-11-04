import { AnswerResponse } from '../types.ts';

export const mockAnsweredFixture: AnswerResponse = {
  abstained: false,
  sentences: [
    {
      text: "The roadmap outlines core prerequisites including linear algebra, differential calculus, and probability.",
      citations: ["chunk-1"],
    },
    {
      text: "After fundamentals, engineers implement transformer architectures from scratch and fine-tune open-weight models.",
      citations: ["chunk-2"],
    },
    {
      text: "Evaluation harnesses and retrieval verification are essential before deploying models to high-throughput environments.",
      citations: ["chunk-1"],
    },
    {
      text: "Continuous monitoring ensures latency spikes and distribution drift are caught early in production.",
      citations: [], // unsupported claim, plain text, no mark
    },
  ],
  chunks: {
    "chunk-1": {
      id: "chunk-1",
      doc_id: "doc-101",
      filename: "AI_Engineer_Roadmap.pdf",
      page: 1,
      char_count: 512,
      text: "Pre-requisites: Linear algebra (vector spaces, matrix multiplication), multivariable calculus (gradients, chain rule), and probability theory. These form the computational backbone of modern neural network optimization and loss landscapes.",
      indexed_at: "2026-10-18T10:30:00Z",
      scores: {
        dense: 0.88,
        sparse: 0.74,
        rerank: 0.94,
      },
    },
    "chunk-2": {
      id: "chunk-2",
      doc_id: "doc-101",
      filename: "AI_Engineer_Roadmap.pdf",
      page: 3,
      char_count: 480,
      text: "Core Architectures: Transformer attention mechanisms, rotary position embeddings (RoPE), and KV-caching. Engineers must understand forward-backward passes and parameter-efficient fine-tuning (LoRA, QLoRA) across open-source model weights.",
      indexed_at: "2026-10-18T10:30:00Z",
      scores: {
        dense: 0.82,
        sparse: 0.69,
        rerank: 0.89,
      },
    },
  },
  timings: {
    retrieval_ms: 42,
    rerank_ms: 210,
    llm_ms: 890,
  },
};

export const mockAbstainedFixture: AnswerResponse = {
  abstained: true,
  reason: "The indexed documents contain no references to quantum computing or cryogenic memory architectures.",
  sentences: [],
  chunks: {},
  timings: {
    retrieval_ms: 38,
    rerank_ms: 0,
    llm_ms: 210,
  },
};
