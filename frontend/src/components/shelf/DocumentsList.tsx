import React from 'react';
import { Trash2 } from 'lucide-react';
import { useDocsStore } from '../../stores/docsStore.ts';
import { useAuthStore } from '../../stores/authStore.ts';
import { DocItem } from '../../types.ts';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const DocumentsList: React.FC = () => {
  const { docs, isLoading, deleteDoc } = useDocsStore();
  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.role === 'admin';

  if (isLoading && docs.length === 0) {
    return <div className="text-xs font-mono text-secondary py-2">Loading documents…</div>;
  }

  if (docs.length === 0) {
    return (
      <div className="text-xs font-mono text-secondary py-3">
        {isAdmin ? 'No documents yet. Drop a PDF or TXT to start.' : 'No documents uploaded yet.'}
      </div>
    );
  }

  return (
    <ul className="space-y-2 overflow-y-auto max-h-56">
      {docs.map((doc: DocItem) => {
        const isProcessing = doc.status === 'PENDING' || doc.status === 'PROCESSING';
        const isFailed = doc.status === 'FAILED';

        return (
          <li
            key={doc.id}
            className="p-2.5 border border-line bg-surface hover:bg-elevated/40 text-xs flex flex-col justify-between rounded-input transition-colors group"
          >
            <div className="flex items-start justify-between">
              <span className="font-sans font-medium text-ink truncate pr-2" title={doc.filename}>
                {doc.filename}
              </span>
              {isAdmin && (
                <button
                  type="button"
                  onClick={() => deleteDoc(doc.id)}
                  title="Delete document"
                  className="text-muted hover:text-danger opacity-0 group-hover:opacity-100 transition-opacity p-0.5 cursor-pointer"
                >
                  <Trash2 size={13} strokeWidth={1.5} />
                </button>
              )}
            </div>

            <div className="flex items-center justify-between text-secondary font-mono mt-1.5 text-xs">
              <span>{formatSize(doc.file_size)}</span>
              <span>
                {isProcessing && <span className="text-mark font-medium">Processing ({doc.progress_percent || 0}%)</span>}
                {isFailed && <span className="text-danger font-medium">Failed</span>}
                {!isProcessing && !isFailed && `${doc.total_chunks} chunks`}
              </span>
            </div>

            {doc.error_message && (
              <div className="text-danger text-xs font-sans mt-1">
                {doc.error_message}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
};
