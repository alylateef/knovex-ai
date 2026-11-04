import { create } from 'zustand';
import { RAGMode, TopK } from '../types.ts';
import { apiAskQuestion } from '../api.ts';
import { useThreadsStore } from './threadsStore.ts';

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
      created_at: new Date().toISOString(),
    };

    // If no active thread yet, we'll let the backend create one
    // Append optimistic message to active thread (or a temporary "pending" thread id)
    const pendingThreadId = activeThreadId ?? '__pending__';
    threadsStore.appendMessage(pendingThreadId, optimisticMsg);

    set({ isSubmitting: true });

    let receivedConvId = activeThreadId;
    let chunksMap: Record<string, any> = {};

    try {
      const { answer, conversation_id } = await apiAskQuestion({
        question,
        top_k: topK,
        mode,
        conversation_id: activeThreadId ?? undefined,
        onMetadata: (chunks, convId) => {
          if (convId) receivedConvId = convId;
          chunksMap = chunks;
        },
        onDelta: (_delta, accumulated) => {
          const targetThreadId = receivedConvId ?? pendingThreadId;
          threadsStore.updateMessage(targetThreadId, tempId, {
            loading: false,
            answer: {
              sentences: [{ text: accumulated, citations: Object.keys(chunksMap) }],
              chunks: chunksMap,
              timings: { retrieval_ms: 150, rerank_ms: 250, llm_ms: 500 },
              abstained: false,
            },
          });
        },
      });

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
                m.id === tempId ? { ...m, answer, loading: false } : m
              ),
            },
          };
        });

        // Re-fetch thread list so title is correct
        threadsStore.fetchThreads();
      } else {
        // Update message in existing thread
        threadsStore.updateMessage(conversation_id, tempId, { answer, loading: false });

        // Refresh the thread's updated_at in the list
        threadsStore.updateThread(conversation_id, { updated_at: new Date().toISOString() });
      }

      set({ isSubmitting: false });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Failed to query documents';

      const currentActive = useThreadsStore.getState().activeThreadId;
      const targetThread = currentActive ?? '__pending__';
      useThreadsStore.getState().updateMessage(targetThread, tempId, {
        error: errMsg,
        loading: false,
      });
      set({ isSubmitting: false });
    }
  },
}));
