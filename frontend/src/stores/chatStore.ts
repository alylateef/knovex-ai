import { create } from 'zustand';
import { RAGMode, TopK } from '../types.ts';
import { apiAskQuestion } from '../api.ts';
import { useThreadsStore } from './threadsStore.ts';
import { SmoothStreamer } from '../lib/smoothStreamer.ts';

interface ChatState {
  isSubmitting: boolean;
  ask: (question: string, topK: TopK, mode: RAGMode) => Promise<void>;
}

export const useChatStore = create<ChatState>((set) => ({
  isSubmitting: false,

  ask: async (question: string, topK: TopK, mode: RAGMode) => {
    const threadsStore = useThreadsStore.getState();
    const activeThreadId = threadsStore.activeThreadId;

    const tempId = `msg-${Date.now()}`;
    const optimisticMsg = {
      id: tempId,
      question,
      loading: true as const,
      streaming: false,
      created_at: new Date().toISOString(),
    };

    const targetThreadId = activeThreadId ?? '__pending__';
    threadsStore.appendMessage(targetThreadId, optimisticMsg);

    set({ isSubmitting: true });

    let chunksMap: Record<string, any> = {};

    const streamer = new SmoothStreamer((smoothText) => {
      threadsStore.updateMessage(targetThreadId, tempId, {
        loading: false,
        streaming: true,
        answer: {
          sentences: [{ text: smoothText, citations: Object.keys(chunksMap) }],
          chunks: chunksMap,
          timings: { retrieval_ms: 0, rerank_ms: 0, llm_ms: 0 },
          abstained: false,
        },
      });
    });

    try {
      const { answer, conversation_id } = await apiAskQuestion({
        question,
        top_k: topK,
        mode,
        conversation_id: activeThreadId ?? undefined,
        onMetadata: (chunks) => {
          chunksMap = chunks;
        },
        onDelta: (_delta, accumulated) => {
          streamer.append(accumulated);
        },
      });

      // Smoothly flush any remaining characters in the 60fps animation buffer
      await streamer.finish();

      const wasNew = !activeThreadId;

      if (wasNew) {
        // Backend created a new conversation — register it in the threads store
        const newThread = {
          id: conversation_id,
          tenant_id: '',
          user_id: '',
          title: question.slice(0, 60),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };

        // Move the pending messages into the real thread id
        const state = useThreadsStore.getState();
        const pendingMsgs = state.messagesByThread['__pending__'] ?? [];
        threadsStore.addThread(newThread);

        // Replace the pending message in the real thread
        useThreadsStore.setState((s) => {
          const withoutPending: Record<string, typeof pendingMsgs> = { ...s.messagesByThread };
          delete withoutPending['__pending__'];
          return {
            messagesByThread: {
              ...withoutPending,
              [conversation_id]: pendingMsgs.map((m) =>
                m.id === tempId ? { ...m, answer, loading: false, streaming: false } : m
              ),
            },
          };
        });

        // Re-fetch thread list so title is correct
        threadsStore.fetchThreads();
      } else {
        // Update message in existing thread
        threadsStore.updateMessage(conversation_id, tempId, { answer, loading: false, streaming: false });

        // Refresh the thread's updated_at in the list
        threadsStore.updateThread(conversation_id, { updated_at: new Date().toISOString() });
      }

      set({ isSubmitting: false });
    } catch (err) {
      streamer.stop();
      const errMsg = err instanceof Error ? err.message : 'Failed to query documents';

      useThreadsStore.getState().updateMessage(targetThreadId, tempId, {
        error: errMsg,
        loading: false,
        streaming: false,
      });
      set({ isSubmitting: false });
    }
  },
}));
