export type UserRole = 'admin' | 'user' | 'viewer';

export interface User {
  id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  organization_name?: string;
  org_code?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
  user_id: string;
  tenant_id: string;
  role: string;
  email: string;
}

export interface DocItem {
  id: string;
  tenant_id: string;
  filename: string;
  file_size: number;
  mime_type: string;
  total_pages: number | null;
  total_chunks: number;
  created_at: string;
  status?: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  progress_percent?: number;
  error_message?: string | null;
}

export interface IngestionStatus {
  id: string;
  document_id: string;
  tenant_id: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  progress_percent: number;
  error_message: string | null;
  retry_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ChunkScores {
  dense?: number;
  sparse?: number;
  rerank?: number;
}

export interface SourceChunk {
  id: string;
  doc_id: string;
  filename: string;
  page: number;
  char_count: number;
  text: string;
  indexed_at?: string;
  scores: ChunkScores;
}

export interface ClaimSentence {
  text: string;
  citations: string[]; // chunk ids
}

export interface Timings {
  retrieval_ms: number;
  rerank_ms: number;
  llm_ms: number;
}

export interface AnswerResponse {
  sentences: ClaimSentence[];
  chunks: Record<string, SourceChunk>;
  timings: Timings;
  abstained: boolean;
  reason?: string;
}

export type RAGMode = 'dense' | 'hybrid' | 'rerank';
export type TopK = 3 | 5 | 8;
export type Theme = 'light' | 'dark';

export interface MessageItem {
  id: string;
  question: string;
  answer?: AnswerResponse;
  loading?: boolean;
  error?: string;
  created_at: string;
}

// ------------------------------------------------------------------
// M2 Thread (Conversation) Types
// ------------------------------------------------------------------

export interface Thread {
  id: string;
  tenant_id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ThreadGroup {
  label: 'Today' | 'Yesterday' | 'Earlier';
  threads: Thread[];
}

/** Raw message shape returned by GET /chat/conversations/{id} */
export interface BackendMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Array<{
    document_id: string;
    filename: string;
    page_number: number;
    chunk_index: number;
    snippet: string;
    relevance_score: number;
    validated: boolean;
  }> | null;
  evidence_status: string;
  created_at: string;
}

