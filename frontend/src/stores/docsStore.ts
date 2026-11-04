import { create } from 'zustand';
import { DocItem } from '../types.ts';
import {
  apiListDocuments,
  apiUploadDocument,
  apiGetIngestionStatus,
  apiDeleteDocument,
} from '../api.ts';

interface DocsState {
  docs: DocItem[];
  isLoading: boolean;
  isUploading: boolean;
  error: string | null;
  pollTimer: number | null;
  fetchDocs: () => Promise<void>;
  uploadDoc: (file: File) => Promise<void>;
  deleteDoc: (docId: string) => Promise<void>;
  startPollingIfNeeded: () => void;
  stopPolling: () => void;
  reset: () => void;
}

export const useDocsStore = create<DocsState>((set, get) => ({
  docs: [],
  isLoading: false,
  isUploading: false,
  error: null,
  pollTimer: null,

  fetchDocs: async () => {
    set({ isLoading: true, error: null });
    try {
      const docs = await apiListDocuments();
      set({ docs, isLoading: false });
      get().startPollingIfNeeded();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch documents';
      set({ isLoading: false, error: msg });
    }
  },

  uploadDoc: async (file: File) => {
    set({ isUploading: true, error: null });
    try {
      const res = await apiUploadDocument(file);
      // Optimistically add document in pending state
      const optimistic: DocItem = {
        id: res.document_id,
        tenant_id: '',
        filename: res.filename,
        file_size: file.size,
        mime_type: file.type || 'application/octet-stream',
        total_pages: null,
        total_chunks: 0,
        created_at: new Date().toISOString(),
        status: 'PENDING',
        progress_percent: 0,
      };
      set((state) => ({
        docs: [optimistic, ...state.docs.filter((d) => d.id !== res.document_id)],
        isUploading: false,
      }));
      get().startPollingIfNeeded();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      set({ isUploading: false, error: msg });
      throw err;
    }
  },

  deleteDoc: async (docId: string) => {
    try {
      await apiDeleteDocument(docId);
      set((state) => ({
        docs: state.docs.filter((d) => d.id !== docId),
      }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Delete failed';
      set({ error: msg });
      throw err;
    }
  },

  startPollingIfNeeded: () => {
    const { docs, pollTimer } = get();
    const hasUnfinished = docs.some(
      (d) => d.status === 'PENDING' || d.status === 'PROCESSING'
    );

    if (hasUnfinished && !pollTimer) {
      const timer = window.setInterval(async () => {
        const currentDocs = get().docs;
        const unfinished = currentDocs.filter(
          (d) => d.status === 'PENDING' || d.status === 'PROCESSING'
        );

        if (unfinished.length === 0) {
          get().stopPolling();
          return;
        }

        try {
          let anyFinished = false;
          const updated = await Promise.all(
            currentDocs.map(async (doc) => {
              if (doc.status === 'PENDING' || doc.status === 'PROCESSING') {
                try {
                  const statusObj = await apiGetIngestionStatus(doc.id);
                  if (statusObj.status === 'COMPLETED' || statusObj.status === 'FAILED') {
                    anyFinished = true;
                  }
                  return {
                    ...doc,
                    status: statusObj.status,
                    progress_percent: statusObj.progress_percent,
                    error_message: statusObj.error_message,
                  };
                } catch {
                  return doc;
                }
              }
              return doc;
            })
          );
          set({ docs: updated });
          if (anyFinished) {
            // Re-fetch document list from server to get accurate total_chunks count
            const freshDocs = await apiListDocuments();
            set({ docs: freshDocs });
          }
        } catch {
          // ignore transient poll failure
        }
      }, 2500);

      set({ pollTimer: timer });
    } else if (!hasUnfinished && pollTimer) {
      get().stopPolling();
    }
  },

  stopPolling: () => {
    const { pollTimer } = get();
    if (pollTimer) {
      clearInterval(pollTimer);
      set({ pollTimer: null });
    }
  },

  reset: () => {
    get().stopPolling();
    set({
      docs: [],
      isLoading: false,
      isUploading: false,
      error: null,
    });
  },
}));
