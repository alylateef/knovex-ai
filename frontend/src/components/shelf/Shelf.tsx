import React, { useEffect } from 'react';
import { Plus, X } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore.ts';
import { useDocsStore } from '../../stores/docsStore.ts';
import { useThreadsStore } from '../../stores/threadsStore.ts';
import { useUIStore } from '../../stores/uiStore.ts';
import { UploadDropzone } from './UploadDropzone.tsx';
import { DocumentsList } from './DocumentsList.tsx';
import { ThreadList } from './ThreadList.tsx';

/* ------------------------------------------------------------------ */
/* Knovex wordmark — pure SVG, no external dep                          */
/* ------------------------------------------------------------------ */
const KnovexWordmark: React.FC = () => (
  <div className="flex items-center space-x-2.5 select-none">
    <img
      src="/logo.svg"
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
  const { sidebarOpen, setSidebarOpen } = useUIStore();

  useEffect(() => {
    fetchDocs();
    fetchThreads();
  }, [fetchDocs, fetchThreads]);

  const handleNewThread = () => {
    void setActiveThread(null);
    setSidebarOpen(false);
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {sidebarOpen && (
        <div
          role="button"
          tabIndex={0}
          aria-label="Close sidebar"
          onClick={() => setSidebarOpen(false)}
          onKeyDown={(e) => { if (e.key === 'Escape') setSidebarOpen(false); }}
          className="fixed inset-0 bg-black/40 backdrop-blur-xs z-40 md:hidden transition-opacity cursor-pointer"
        />
      )}

      <aside
        className={`
          fixed md:static inset-y-0 left-0 z-50
          w-72 md:w-shelf shrink-0
          border-r border-line bg-sidebar flex flex-col h-full overflow-hidden
          transition-transform duration-200 ease-in-out
          ${sidebarOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full md:translate-x-0'}
        `}
      >

        {/* ── Brand header ── */}
        <div className="px-4 pt-4 pb-3 border-b border-line shrink-0">
          <div className="flex items-center justify-between">
            <KnovexWordmark />
            <button
              type="button"
              onClick={() => setSidebarOpen(false)}
              aria-label="Close sidebar"
              className="md:hidden p-1 text-secondary hover:text-ink rounded-lg transition-colors cursor-pointer"
            >
              <X size={16} strokeWidth={1.75} />
            </button>
          </div>
          <div className="mt-2 flex items-center space-x-2">
            <div className="w-1.5 h-1.5 rounded-chip bg-mark shrink-0" />
            <span className="text-xs font-mono text-secondary truncate font-medium" title={user?.organization_name || user?.email}>
              {user?.organization_name || user?.email.split('@')[1] || 'workspace'}
            </span>
            <span className="text-xs font-mono text-muted">·</span>
            <span className="text-xs font-mono text-secondary capitalize shrink-0">{user?.role || 'user'}</span>
          </div>
        </div>

      {/* ── Scrollable middle: threads only ── */}
      <div className="flex-1 min-h-0 overflow-y-auto">

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

      </div>

      {/* ── Pinned bottom section: Documents + Upload + Footer ── */}
      <div className="shrink-0 border-t border-line">

        {/* ── Documents ── */}
        <div className="pt-3 pb-2 px-4">
          <div className="text-xs font-mono text-secondary uppercase tracking-wider font-medium mb-2">
            Documents
          </div>
          <DocumentsList />
        </div>

        {/* ── Upload (Admin only) ── */}
        {user?.role === 'admin' && (
          <div className="px-4 pb-3">
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
          {user?.org_code && (
            <div className="text-[10px] font-mono text-muted flex items-center gap-1 mt-0.5" title="Share this code with teammates to join your workspace">
              <span>Code:</span>
              <span className="font-semibold text-secondary select-all">{user.org_code}</span>
            </div>
          )}
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
  </>
  );
};
