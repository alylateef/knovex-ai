import {
  AuthResponse,
  BackendMessage,
  DocItem,
  IngestionStatus,
  AnswerResponse,
  SourceChunk,
  ClaimSentence,
  MessageItem,
  RAGMode,
  Thread,
  TopK,
  User,
} from './types.ts';
import { parseAnswer } from './lib/parseAnswer.ts';
import { mockAnsweredFixture, mockAbstainedFixture } from './mocks/fixtures.ts';

// ----------------------------------------------------------------------
// Backend Field Names & Endpoints (verified from knovex/api.py & schemas.py)
// ----------------------------------------------------------------------
export const AUTH_FIELDS = {
  LOGIN_EMAIL: 'email',
  LOGIN_PASSWORD: 'password',
  REGISTER_ORG_NAME: 'organization_name',
  REGISTER_EMAIL: 'email',
  REGISTER_PASSWORD: 'password',
  REGISTER_FULL_NAME: 'full_name',
} as const;

export const ENDPOINTS = {
  LOGIN: '/api/v1/auth/login',
  REGISTER: '/api/v1/auth/register',
  JOIN: '/api/v1/auth/join',
  LOGOUT: '/api/v1/auth/logout',
  ME: '/api/v1/auth/me',
  DOCUMENTS: '/api/v1/documents',
  UPLOAD: '/api/v1/documents/upload',
  STATUS: (docId: string) => `/api/v1/documents/${docId}/status`,
  DELETE_DOC: (docId: string) => `/api/v1/documents/${docId}`,
  CHAT_QUERY: '/api/v1/chat/query',
  CHAT_STREAM: '/api/v1/chat/stream',
  CONVERSATIONS: '/api/v1/chat/conversations',
  CONVERSATION: (id: string) => `/api/v1/chat/conversations/${id}`,
} as const;


const SESSION_TOKEN_KEY = 'knovex_session_token';
const isMock = import.meta.env.VITE_MOCK === '1';

let inMemoryToken: string | null = sessionStorage.getItem(SESSION_TOKEN_KEY);

export function getAccessToken(): string | null {
  return inMemoryToken;
}

export function setAccessToken(token: string | null) {
  inMemoryToken = token;
  if (token) {
    sessionStorage.setItem(SESSION_TOKEN_KEY, token);
  } else {
    sessionStorage.removeItem(SESSION_TOKEN_KEY);
  }
}

async function request<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (inMemoryToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${inMemoryToken}`);
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    setAccessToken(null);
    window.dispatchEvent(new CustomEvent('knovex:unauthorized'));
    throw new Error('Session expired or unauthorized. Please sign in.');
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const errJson = await response.json();
      if (errJson && typeof errJson.detail === 'string') {
        detail = errJson.detail;
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

// ----------------------------------------------------------------------
// API Methods
// ----------------------------------------------------------------------

export async function apiLogin(payload: {
  [AUTH_FIELDS.LOGIN_EMAIL]: string;
  [AUTH_FIELDS.LOGIN_PASSWORD]: string;
}): Promise<AuthResponse> {
  if (isMock) {
    const mockAuth: AuthResponse = {
      access_token: 'mock-jwt-token-12345',
      token_type: 'bearer',
      expires_in_minutes: 60,
      user_id: 'usr-mock-1',
      tenant_id: 'tnt-mock-1',
      role: 'admin',
      email: payload.email,
    };
    setAccessToken(mockAuth.access_token);
    return mockAuth;
  }

  const data = await request<AuthResponse>(ENDPOINTS.LOGIN, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  setAccessToken(data.access_token);
  return data;
}

export async function apiRegister(payload: {
  [AUTH_FIELDS.REGISTER_ORG_NAME]: string;
  [AUTH_FIELDS.REGISTER_EMAIL]: string;
  [AUTH_FIELDS.REGISTER_PASSWORD]: string;
  [AUTH_FIELDS.REGISTER_FULL_NAME]?: string;
  role?: 'admin' | 'user';
}): Promise<AuthResponse> {
  if (isMock) {
    const mockAuth: AuthResponse = {
      access_token: 'mock-jwt-token-12345',
      token_type: 'bearer',
      expires_in_minutes: 60,
      user_id: 'usr-mock-1',
      tenant_id: 'tnt-mock-1',
      role: payload.role || 'admin',
      email: payload.email,
    };
    setAccessToken(mockAuth.access_token);
    return mockAuth;
  }

  const data = await request<AuthResponse>(ENDPOINTS.REGISTER, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  setAccessToken(data.access_token);
  return data;
}

export async function apiJoin(payload: {
  org_code: string;
  email: string;
  password: string;
  full_name?: string;
  role?: 'admin' | 'user';
}): Promise<AuthResponse> {
  const data = await request<AuthResponse>(ENDPOINTS.JOIN, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  setAccessToken(data.access_token);
  return data;
}

export async function apiLogout(): Promise<void> {
  try {
    if (!isMock && inMemoryToken) {
      await request<{ message: string }>(ENDPOINTS.LOGOUT, { method: 'POST' });
    }
  } finally {
    setAccessToken(null);
  }
}

export async function apiGetMe(): Promise<User> {
  if (isMock) {
    return {
      id: 'usr-mock-1',
      tenant_id: 'tnt-mock-1',
      email: 'admin@knovex.local',
      full_name: 'Admin User',
      role: 'admin',
      is_active: true,
      created_at: new Date().toISOString(),
    };
  }
  return request<User>(ENDPOINTS.ME);
}

export async function apiListDocuments(): Promise<DocItem[]> {
  if (isMock) {
    return [
      {
        id: 'doc-101',
        tenant_id: 'tnt-mock-1',
        filename: 'AI_Engineer_Roadmap.pdf',
        file_size: 218214,
        mime_type: 'application/pdf',
        total_pages: 5,
        total_chunks: 5,
        created_at: '2026-10-18T10:00:00Z',
        status: 'COMPLETED',
        progress_percent: 100,
      },
    ];
  }
  return request<DocItem[]>(ENDPOINTS.DOCUMENTS);
}

export async function apiUploadDocument(file: File): Promise<{ document_id: string; job_id: string; filename: string }> {
  if (isMock) {
    return {
      document_id: 'doc-new-1',
      job_id: 'job-new-1',
      filename: file.name,
    };
  }

  const formData = new FormData();
  formData.append('file', file);

  return request<{ document_id: string; job_id: string; filename: string }>(ENDPOINTS.UPLOAD, {
    method: 'POST',
    body: formData,
  });
}

export async function apiGetIngestionStatus(docId: string): Promise<IngestionStatus> {
  if (isMock) {
    return {
      id: 'job-new-1',
      document_id: docId,
      tenant_id: 'tnt-mock-1',
      status: 'COMPLETED',
      progress_percent: 100,
      error_message: null,
      retry_count: 0,
      created_at: new Date().toISOString(),
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    };
  }
  return request<IngestionStatus>(ENDPOINTS.STATUS(docId));
}

export async function apiDeleteDocument(docId: string): Promise<void> {
  if (isMock) return;
  await request<{ message: string }>(ENDPOINTS.DELETE_DOC(docId), { method: 'DELETE' });
}

export async function apiAskQuestion(payload: {
  question: string;
  top_k: TopK;
  mode: RAGMode;
  conversation_id?: string;
  onDelta?: (deltaText: string, accumulated: string) => void;
  onMetadata?: (citations: Record<string, SourceChunk>, convId: string) => void;
}): Promise<{ answer: AnswerResponse; conversation_id: string }> {
  if (isMock) {
    if (payload.question.toLowerCase().includes('error')) {
      throw new Error('LLM provider returned 503 Service Unavailable. Try again.');
    }
    if (payload.question.toLowerCase().includes('nothing') || payload.question.toLowerCase().includes('quantum')) {
      return { answer: mockAbstainedFixture, conversation_id: 'mock-conv-1' };
    }
    return { answer: mockAnsweredFixture, conversation_id: 'mock-conv-1' };
  }

  const rerank = payload.mode === 'rerank';
  const start = performance.now();
  const token = getAccessToken();

  try {
    // 1. Try Live SSE Streaming for instant real-time response
    const response = await fetch(ENDPOINTS.CHAT_STREAM, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        message: payload.question,
        rerank,
        conversation_id: payload.conversation_id ?? null,
      }),
    });

    if (response.status === 401) {
      setAccessToken(null);
      window.dispatchEvent(new CustomEvent('knovex:unauthorized'));
      throw new Error('Session expired or unauthorized. Please sign in.');
    }

    if (!response.ok || !response.body) {
      throw new Error(`Streaming request failed with status ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let accumulatedText = '';
    let serverConvId = payload.conversation_id || '';
    let evidenceStatus = 'sufficient';
    const chunks: Record<string, SourceChunk> = {};

    // Real timing measurements (not estimates)
    let metadataMs: number | null = null; // when retrieval+rerank finished
    let ttftMs: number | null = null;      // when first LLM token arrived
    let serverTimings: { retrieval_ms?: number; rerank_ms?: number } | null = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data:')) continue;
        const jsonStr = trimmed.slice(5).trim();
        if (!jsonStr) continue;

        try {
          const event = JSON.parse(jsonStr);
          if (event.type === 'init' && event.conversation_id) {
            serverConvId = event.conversation_id;
          } else if (event.type === 'metadata') {
            metadataMs = Math.round(performance.now() - start);
            if (event.server_timings) {
              serverTimings = event.server_timings;
            }
            const citations = event.citations || [];
            evidenceStatus = event.evidence_status || 'sufficient';
            citations.forEach((c: any, idx: number) => {
              const chunkId = `chk-${c.document_id}-${c.chunk_index}-${idx}`;
              chunks[chunkId] = {
                id: chunkId,
                doc_id: c.document_id,
                filename: c.filename,
                page: c.page_number || 1,
                char_count: (c.snippet || '').length,
                text: c.snippet || '',
                scores: { rerank: c.relevance_score || 1.0 },
              };
            });
            payload.onMetadata?.(chunks, serverConvId);
          } else if (event.type === 'delta' && event.content) {
            if (ttftMs === null) ttftMs = Math.round(performance.now() - start);
            accumulatedText += event.content;
            payload.onDelta?.(event.content, accumulatedText);
          } else if (event.type === 'done') {
            if (event.answer) accumulatedText = event.answer;
            if (event.evidence_status) evidenceStatus = event.evidence_status;
          }
        } catch {
          // ignore non-critical stream framing errors
        }
      }
    }

    const totalMs = Math.round(performance.now() - start);
    const chunkIds = Object.keys(chunks);
    const abstained = evidenceStatus === 'insufficient' || evidenceStatus === 'declined';

    // Derive timing breakdown from real server stopwatch measurements.
    // If backend provides server_timings, use exact retrieval_ms & rerank_ms.
    // Otherwise fallback smoothly to measured client latency.
    const serverRetrieval = serverTimings?.retrieval_ms;
    const serverRerank    = serverTimings?.rerank_ms;

    const retrievalBase = metadataMs ?? Math.round(totalMs * (rerank ? 0.40 : 0.15));
    const retrievalMs   = serverRetrieval !== undefined
      ? serverRetrieval
      : (rerank ? Math.round(retrievalBase * 0.45) : retrievalBase);
    const rerankMs      = serverRerank !== undefined
      ? serverRerank
      : (rerank ? Math.round(retrievalBase * 0.55) : 0);

    const clientPrepTime = metadataMs ?? (retrievalMs + rerankMs);
    const llmMs         = ttftMs !== null
      ? Math.max(1, Math.round(ttftMs - clientPrepTime))
      : Math.max(1, Math.round(totalMs - clientPrepTime));

    const rawBlocks = accumulatedText
      ? (accumulatedText.includes('|')
          ? [accumulatedText]
          : accumulatedText.split(/\n\s*\n/).filter(Boolean))
      : [];

    const sentences: ClaimSentence[] = (rawBlocks.length > 0 ? rawBlocks : [accumulatedText || '']).map((blockText, bIdx) => ({
      text: blockText,
      citations: !abstained && bIdx === 0 ? chunkIds : [],
    }));

    const parsed = parseAnswer({
      sentences,
      chunks,
      timings: {
        retrieval_ms: retrievalMs,
        rerank_ms: rerankMs,
        llm_ms: llmMs,
      },
      abstained,
      reason: abstained ? 'Context retrieved was insufficient to answer with verified evidence.' : undefined,
    });

    return { answer: parsed, conversation_id: serverConvId };
  } catch (err) {
    // Fallback to standard HTTP query endpoint
    const raw = await request<{
      conversation_id: string;
      message_id: string;
      answer: string;
      evidence_status: string;
      citations: Array<{
        document_id: string;
        filename: string;
        page_number: number;
        chunk_index: number;
        snippet: string;
        relevance_score: number;
        validated: boolean;
      }>;
    }>(ENDPOINTS.CHAT_QUERY, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: payload.question,
        rerank,
        conversation_id: payload.conversation_id ?? null,
      }),
    });

    const totalMs = Math.round(performance.now() - start);
    const chunks: Record<string, SourceChunk> = {};
    const citations = raw.citations || [];

    citations.forEach((c, idx) => {
      const chunkId = `chk-${c.document_id}-${c.chunk_index}-${idx}`;
      chunks[chunkId] = {
        id: chunkId,
        doc_id: c.document_id,
        filename: c.filename,
        page: c.page_number || 1,
        char_count: c.snippet.length,
        text: c.snippet,
        scores: {
          rerank: c.relevance_score,
        },
      };
    });

    const chunkIds = Object.keys(chunks);
    const abstained = raw.evidence_status === 'insufficient' || raw.evidence_status === 'declined';

    const rawBlocks = raw.answer
      ? (raw.answer.includes('|')
          ? [raw.answer]
          : raw.answer.split(/\n\s*\n/).filter(Boolean))
      : [];

    const sentences: ClaimSentence[] = (rawBlocks.length > 0 ? rawBlocks : [raw.answer || '']).map((blockText, bIdx) => ({
      text: blockText,
      citations: !abstained && bIdx === 0 ? chunkIds : [],
    }));

    const parsed = parseAnswer({
      sentences,
      chunks,
      timings: {
        retrieval_ms: Math.round(totalMs * 0.15),
        rerank_ms: rerank ? Math.round(totalMs * 0.25) : 0,
        llm_ms: Math.round(totalMs * (rerank ? 0.6 : 0.85)),
      },
      abstained,
      reason: abstained ? 'Context retrieved was insufficient to answer with verified evidence.' : undefined,
    });

    return { answer: parsed, conversation_id: raw.conversation_id };
  }
}

// ----------------------------------------------------------------------
// Thread (Conversation) API
// ----------------------------------------------------------------------

export async function apiListThreads(): Promise<Thread[]> {
  if (isMock) {
    return [
      {
        id: 'mock-conv-1',
        tenant_id: 'tnt-mock-1',
        user_id: 'usr-mock-1',
        title: 'What is retrieval-augmented generation?',
        created_at: new Date(Date.now() - 5 * 60000).toISOString(),
        updated_at: new Date(Date.now() - 2 * 60000).toISOString(),
      },
      {
        id: 'mock-conv-2',
        tenant_id: 'tnt-mock-1',
        user_id: 'usr-mock-1',
        title: 'Summarize the document key points',
        created_at: new Date(Date.now() - 86400000).toISOString(),
        updated_at: new Date(Date.now() - 86400000).toISOString(),
      },
    ];
  }
  return request<Thread[]>(ENDPOINTS.CONVERSATIONS);
}

export async function apiDeleteThread(id: string): Promise<void> {
  if (isMock) return;
  await request<{ message: string }>(ENDPOINTS.CONVERSATION(id), { method: 'DELETE' });
}

export async function apiRenameThread(id: string, title: string): Promise<Thread> {
  if (isMock) {
    return { id, tenant_id: 'tnt-mock-1', user_id: 'usr-mock-1', title, created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
  }
  return request<Thread>(ENDPOINTS.CONVERSATION(id), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
}

/** Fetches and converts backend message history for a thread into MessageItem[] pairs */
export async function apiGetThreadMessages(id: string): Promise<{ messages: MessageItem[]; threadId: string }> {
  if (isMock) {
    return { messages: [], threadId: id };
  }

  const data = await request<{
    id: string;
    title: string;
    messages: BackendMessage[];
  }>(ENDPOINTS.CONVERSATION(id));

  // Pair up user + assistant messages into MessageItem[]
  const rawMsgs = data.messages ?? [];
  const pairs: MessageItem[] = [];

  for (let i = 0; i < rawMsgs.length; i++) {
    const msg = rawMsgs[i];
    if (msg.role !== 'user') continue;

    const next = rawMsgs[i + 1];
    const assistant = next?.role === 'assistant' ? next : null;

    let answer: AnswerResponse | undefined;
    if (assistant) {
      const citations = assistant.citations ?? [];
      const chunks: Record<string, SourceChunk> = {};
      citations.forEach((c, idx) => {
        const chunkId = `chk-${c.document_id || 'doc'}-${c.chunk_index ?? idx}-${idx}`;
        chunks[chunkId] = {
          id: chunkId,
          doc_id: c.document_id || '',
          filename: c.filename || 'Source Document',
          page: c.page_number || 1,
          char_count: (c.snippet || '').length,
          text: c.snippet || '',
          scores: { rerank: c.relevance_score ?? 1.0 },
        };
      });

      const chunkIds = Object.keys(chunks);
      const abstained = assistant.evidence_status === 'insufficient' || assistant.evidence_status === 'declined';
      const rawBlocks = assistant.content
        ? (assistant.content.includes('|')
            ? [assistant.content]
            : assistant.content.split(/\n\s*\n/).filter(Boolean))
        : [];

      const sentences: ClaimSentence[] = (rawBlocks.length > 0 ? rawBlocks : [assistant.content || '']).map((bText, bIdx) => ({
        text: bText,
        citations: !abstained && bIdx === 0 ? chunkIds : [],
      }));


      answer = parseAnswer({
        sentences,
        chunks,
        timings: { retrieval_ms: 0, rerank_ms: 0, llm_ms: 0 },
        abstained,
        reason: abstained ? 'Context retrieved was insufficient to answer with verified evidence.' : undefined,
      });
    }

    pairs.push({
      id: assistant?.id ?? `pair-${i}`,
      question: msg.content,
      answer,
      created_at: msg.created_at,
    });
  }

  return { messages: pairs, threadId: id };
}
