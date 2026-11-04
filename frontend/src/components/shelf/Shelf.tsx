import React, { useEffect } from 'react';
import { Plus } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore.ts';
import { useDocsStore } from '../../stores/docsStore.ts';
import { useThreadsStore } from '../../stores/threadsStore.ts';
import { UploadDropzone } from './UploadDropzone.tsx';
import { DocumentsList } from './DocumentsList.tsx';
import { ThreadList } from './ThreadList.tsx';

/* ------------------------------------------------------------------ */
/* Knovex wordmark — pure SVG, no external dep                          */
/* ------------------------------------------------------------------ */
const KnovexWordmark: React.FC = () => (
  <div className="flex items-center space-x-2.5 select-none">
    <img
      src="/logo.png"
      alt="Knovex AI Logo"
      style={{ width: '22px', height: '22px' }}
      className="rounded-chip object-cover shrink-0"
    />
    <span className="font-sans font-bold text-base text-ink tracking-tight">
      Knovex
    </span>
    <span className="font-mono text-xs text-muted border border-line px-1 py-0 rounded-chip leading-none mt-0.5">
      AI
    </span>
  </div>
);

export const Shelf: React.FC = () => {
  const { user, logout } = useAuthStore();
  const { fetchDocs } = useDocsStore();
  const { fetchThreads, setActiveThread } = useThreadsStore();

  useEffect(() => {
    fetchDocs();
    fetchThreads();
  }, [fetchDocs, fetchThreads]);

  const handleNewThread = () => {
    void setActiveThread(null);
  };

  return (
    <aside className="w-full md:w-shelf shrink-0 border-b md:border-b-0 md:border-r border-line bg-sidebar flex flex-col h-auto md:h-full overflow-hidden">

      {/* ── Brand header ── */}
      <div className="px-4 pt-4 pb-3 border-b border-line shrink-0">
        <KnovexWordmark />
        <div className="mt-2 flex items-center space-x-2">
          <div className="w-1.5 h-1.5 rounded-chip bg-mark" />
          <span className="text-xs font-mono text-secondary truncate" title={user?.email}>
            {user?.email.split('@')[1] || 'workspace'}
          </span>
          <span className="text-xs font-mono text-muted">·</span>
          <span className="text-xs font-mono text-secondary capitalize">{user?.role || 'user'}</span>
        </div>
      </div>

      {/* ── Scrollable middle ── */}
      <div className="flex-1 overflow-y-auto">

        {/* ── Threads ── */}
        <div className="pt-3 pb-2">
          <div className="flex items-center justify-between px-4 mb-2">
            <span className="text-xs font-mono text-secondary uppercase tracking-wider font-medium">
              Threads
            </span>
            <button
              type="button"
              onClick={handleNewThread}
              title="Start new thread"
              aria-label="New thread"
              className="flex items-center space-x-1 text-xs font-mono text-secondary hover:text-mark hover:bg-elevated px-1.5 py-0.5 rounded-chip transition-colors"
            >
              <Plus size={13} strokeWidth={2} />
              <span>New</span>
            </button>
          </div>
          <ThreadList />
        </div>

        {/* ── Divider ── */}
        <div className="h-px bg-line mx-4 my-1" />

        {/* ── Documents ── */}
        <div className="pt-3 pb-4 px-4">
          <div className="text-xs font-mono text-secondary uppercase tracking-wider font-medium mb-2">
            Documents
          </div>
          <DocumentsList />
        </div>

        {/* ── Upload (Admin only) ── */}
        {user?.role === 'admin' && (
          <div className="px-4 pb-4">
            <UploadDropzone />
          </div>
        )}

      </div>

      {/* ── User footer ── */}
      <div className="px-4 py-3 border-t border-line shrink-0 flex items-center justify-between">
        <div className="min-w-0 pr-2">
          <div className="flex items-center gap-1.5">
            <span
              className="text-xs font-sans font-semibold text-ink truncate"
              title={user?.email}
            >
              {user?.email}
            </span>
            <span
              className={`text-[10px] font-mono px-1.5 py-0.2 rounded border uppercase font-medium shrink-0 ${
                user?.role === 'admin'
                  ? 'border-mark/40 text-mark bg-mark/10'
                  : 'border-line text-muted bg-surface'
              }`}
            >
              {user?.role || 'user'}
            </span>
          </div>
        </div>
        <button
          type="button"
          onClick={() => logout()}
          className="text-xs font-mono text-muted hover:text-danger transition-colors shrink-0 cursor-pointer"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
};
