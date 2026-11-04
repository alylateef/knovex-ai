import { create } from 'zustand';
import { Thread, MessageItem } from '../types.ts';
import {
  apiListThreads,
  apiDeleteThread,
  apiRenameThread,
  apiGetThreadMessages,
} from '../api.ts';

interface ThreadsState {
  /** Ordered list of threads (newest first) */
  threads: Thread[];
  /** ID of the currently active/selected thread */
  activeThreadId: string | null;
  /** Messages keyed by threadId, populated on demand */
  messagesByThread: Record<string, MessageItem[]>;
  /** Threads being loaded (fetch in progress) */
  loadingHistory: Record<string, boolean>;
  /** Whether the top-level thread list is being fetched */
  fetchingList: boolean;

  fetchThreads: () => Promise<void>;
  setActiveThread: (id: string | null) => Promise<void>;
  setActiveThreadIdOnly: (id: string) => void;
  addThread: (thread: Thread) => void;
  updateThread: (id: string, patch: Partial<Thread>) => void;
  appendMessage: (threadId: string, msg: MessageItem) => void;
  updateMessage: (threadId: string, msgId: string, patch: Partial<MessageItem>) => void;
  deleteThread: (id: string) => Promise<void>;
  renameThread: (id: string, title: string) => Promise<void>;
  clearThread: (id: string) => void;
  reset: () => void;
}

export const useThreadsStore = create<ThreadsState>((set, get) => ({
  threads: [],
  activeThreadId: null,
  messagesByThread: {},
  loadingHistory: {},
  fetchingList: false,

  fetchThreads: async () => {
    set({ fetchingList: true });
    try {
      const threads = await apiListThreads();
      set({ threads, fetchingList: false });
    } catch {
      set({ fetchingList: false });
    }
  },

  setActiveThread: async (id: string | null) => {
    set({ activeThreadId: id });
    if (!id) return;

    // Skip if already loaded
    const existing = get().messagesByThread[id];
    if (existing) return;

    set((s) => ({ loadingHistory: { ...s.loadingHistory, [id]: true } }));
    try {
      const { messages } = await apiGetThreadMessages(id);
      set((s) => ({
        messagesByThread: { ...s.messagesByThread, [id]: messages },
        loadingHistory: { ...s.loadingHistory, [id]: false },
      }));
    } catch {
      set((s) => ({
        loadingHistory: { ...s.loadingHistory, [id]: false },
      }));
    }
  },

  /** Sets active thread id without fetching history (used right after chat creates it) */
  setActiveThreadIdOnly: (id: string) => {
    set({ activeThreadId: id });
  },

  addThread: (thread: Thread) => {
    set((s) => ({
      threads: [thread, ...s.threads],
      activeThreadId: thread.id,
      messagesByThread: { ...s.messagesByThread, [thread.id]: [] },
    }));
  },

  updateThread: (id: string, patch: Partial<Thread>) => {
    set((s) => ({
      threads: s.threads.map((t) => (t.id === id ? { ...t, ...patch } : t)),
    }));
  },

  appendMessage: (threadId: string, msg: MessageItem) => {
    set((s) => {
      const existing = s.messagesByThread[threadId] ?? [];
      return {
        messagesByThread: { ...s.messagesByThread, [threadId]: [...existing, msg] },
      };
    });
  },

  updateMessage: (threadId: string, msgId: string, patch: Partial<MessageItem>) => {
    set((s) => {
      const existing = s.messagesByThread[threadId] ?? [];
      return {
        messagesByThread: {
          ...s.messagesByThread,
          [threadId]: existing.map((m) => (m.id === msgId ? { ...m, ...patch } : m)),
        },
      };
    });
  },

  deleteThread: async (id: string) => {
    await apiDeleteThread(id);
    set((s) => {
      const remaining = s.threads.filter((t) => t.id !== id);
      const newActive =
        s.activeThreadId === id
          ? (remaining[0]?.id ?? null)
          : s.activeThreadId;
      const msgs = { ...s.messagesByThread };
      delete msgs[id];
      return { threads: remaining, activeThreadId: newActive, messagesByThread: msgs };
    });
    // Load history for newly activated thread if needed
    const { activeThreadId } = get();
    if (activeThreadId && !get().messagesByThread[activeThreadId]) {
      await get().setActiveThread(activeThreadId);
    }
  },

  renameThread: async (id: string, title: string) => {
    const updated = await apiRenameThread(id, title);
    set((s) => ({
      threads: s.threads.map((t) => (t.id === id ? { ...t, ...updated } : t)),
    }));
  },

  clearThread: (id: string) => {
    set((s) => ({
      messagesByThread: { ...s.messagesByThread, [id]: [] },
    }));
  },

  reset: () => {
    set({
      threads: [],
      activeThreadId: null,
      messagesByThread: {},
      loadingHistory: {},
      fetchingList: false,
    });
  },
}));
