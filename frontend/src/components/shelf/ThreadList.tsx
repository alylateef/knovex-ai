import React, { useRef, useState, useCallback } from 'react';
import { MessageSquare, Trash2 } from 'lucide-react';
import { useThreadsStore } from '../../stores/threadsStore.ts';
import { groupThreadsByDate } from '../../lib/groupThreadsByDate.ts';
import { Thread } from '../../types.ts';

interface DeleteConfirmProps {
  onYes: () => void;
  onNo: () => void;
}

const DeleteConfirm: React.FC<DeleteConfirmProps> = ({ onYes, onNo }) => (
  <span className="flex items-center space-x-1 ml-auto shrink-0">
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onYes(); }}
      className="text-danger font-mono text-xs px-1 hover:opacity-80 transition-opacity"
    >
      Yes
    </button>
    <span className="text-muted font-mono text-xs">/</span>
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onNo(); }}
      className="text-muted font-mono text-xs px-1 hover:text-ink transition-colors"
    >
      No
    </button>
  </span>
);

interface ThreadRowProps {
  thread: Thread;
  isActive: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
}

const ThreadRow: React.FC<ThreadRowProps> = ({ thread, isActive, onSelect, onDelete, onRename }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const editRef = useRef<HTMLSpanElement>(null);
  const originalTitle = useRef(thread.title);

  const startEdit = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    originalTitle.current = thread.title;
    setIsEditing(true);
    setTimeout(() => {
      if (editRef.current) {
        editRef.current.focus();
        // Move cursor to end
        const range = document.createRange();
        range.selectNodeContents(editRef.current);
        range.collapse(false);
        window.getSelection()?.removeAllRanges();
        window.getSelection()?.addRange(range);
      }
    }, 0);
  }, [thread.title]);

  const commitEdit = useCallback(() => {
    if (!editRef.current) return;
    const newTitle = editRef.current.innerText.trim();
    setIsEditing(false);
    if (newTitle && newTitle !== originalTitle.current) {
      onRename(thread.id, newTitle);
    } else if (editRef.current) {
      editRef.current.innerText = originalTitle.current;
    }
  }, [onRename, thread.id]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitEdit();
    }
    if (e.key === 'Escape') {
      if (editRef.current) editRef.current.innerText = originalTitle.current;
      setIsEditing(false);
    }
  }, [commitEdit]);

  return (
    <div
      role="button"
      tabIndex={0}
      aria-selected={isActive}
      onClick={() => { if (!isEditing) onSelect(thread.id); }}
      onKeyDown={(e) => { if (e.key === 'Enter' && !isEditing) onSelect(thread.id); }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => { setIsHovered(false); setPendingDelete(false); }}
      className={`
        group relative flex items-start px-2.5 py-2 cursor-pointer select-none
        border-l-2 transition-colors rounded-r-input
        ${isActive
          ? 'border-mark bg-surface text-ink font-medium shadow-sm'
          : 'border-transparent hover:bg-elevated text-secondary hover:text-ink'
        }
      `}
    >
      {/* Thread icon */}
      <MessageSquare
        size={13}
        strokeWidth={1.5}
        className={`shrink-0 mt-0.5 mr-2 transition-colors ${isActive ? 'text-mark' : 'text-muted group-hover:text-secondary'}`}
      />

      {/* Title — double click to rename */}
      <span
        ref={editRef}
        contentEditable={isEditing}
        suppressContentEditableWarning
        onDoubleClick={startEdit}
        onBlur={commitEdit}
        onKeyDown={handleKeyDown}
        className={`
          flex-1 text-xs font-sans leading-snug min-w-0
          ${isEditing
            ? 'outline-none border-b border-mark text-ink whitespace-nowrap overflow-x-auto'
            : 'truncate'
          }
        `}
      >
        {thread.title || 'New Thread'}
      </span>

      {/* Actions: delete confirm or trash icon */}
      {!isEditing && isHovered && (
        pendingDelete ? (
          <DeleteConfirm
            onYes={() => onDelete(thread.id)}
            onNo={() => setPendingDelete(false)}
          />
        ) : (
          <button
            type="button"
            aria-label="Delete thread"
            onClick={(e) => { e.stopPropagation(); setPendingDelete(true); }}
            className="ml-auto shrink-0 text-muted hover:text-danger transition-colors pl-1"
          >
            <Trash2 size={12} strokeWidth={1.5} />
          </button>
        )
      )}
    </div>
  );
};

export const ThreadList: React.FC = () => {
  const { threads, activeThreadId, fetchingList, setActiveThread, deleteThread, renameThread } =
    useThreadsStore();

  const groups = groupThreadsByDate(threads);

  const handleSelect = useCallback(
    (id: string) => {
      if (id !== activeThreadId) {
        void setActiveThread(id);
      }
    },
    [activeThreadId, setActiveThread]
  );

  const handleDelete = useCallback(
    (id: string) => void deleteThread(id),
    [deleteThread]
  );

  const handleRename = useCallback(
    (id: string, title: string) => void renameThread(id, title),
    [renameThread]
  );

  if (fetchingList) {
    return (
      <div className="space-y-1 px-2">
        {[80, 60, 72].map((w) => (
          <div
            key={w}
            className="h-7 bg-elevated/60 rounded-input animate-pulse"
            style={{ width: `${w}%` }}
          />
        ))}
      </div>
    );
  }

  if (threads.length === 0) {
    return (
      <p className="text-xs font-mono text-secondary px-2 py-1">
        No threads yet — ask something to start.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {groups.map((group) => (
        <div key={group.label}>
          <div className="text-xs font-mono text-muted uppercase tracking-wider px-2 mb-1">
            {group.label}
          </div>
          <div className="space-y-0">
            {group.threads.map((thread) => (
              <ThreadRow
                key={thread.id}
                thread={thread}
                isActive={thread.id === activeThreadId}
                onSelect={handleSelect}
                onDelete={handleDelete}
                onRename={handleRename}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};
