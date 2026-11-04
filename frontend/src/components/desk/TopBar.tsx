import React from 'react';
import { Sun, Moon, Menu } from 'lucide-react';
import { useUIStore } from '../../stores/uiStore.ts';
import { useThreadsStore } from '../../stores/threadsStore.ts';

export const TopBar: React.FC = () => {
  const { theme, toggleTheme, toggleSidebar } = useUIStore();
  const { threads, activeThreadId } = useThreadsStore();

  const activeThread = activeThreadId
    ? threads.find((t) => t.id === activeThreadId)
    : null;

  return (
    <header className="h-12 border-b border-line bg-surface px-3 md:px-4 flex items-center justify-between shrink-0">

      {/* Left — mobile menu button + active thread title or system status */}
      <div className="flex items-center space-x-2 md:space-x-3 min-w-0">
        <button
          type="button"
          onClick={toggleSidebar}
          aria-label="Open navigation menu"
          className="md:hidden p-1.5 -ml-1 text-secondary hover:text-ink hover:bg-elevated rounded-lg transition-colors cursor-pointer"
        >
          <Menu size={18} strokeWidth={1.75} />
        </button>

        {/* Status pulse dot */}
        <span
          aria-hidden="true"
          className="w-1.5 h-1.5 rounded-chip bg-mark shrink-0 kx-glow hidden sm:inline-block"
        />

        {activeThread ? (
          <span className="text-xs font-sans font-medium text-ink truncate max-w-prose">
            {activeThread.title}
          </span>
        ) : (
          <span className="text-xs font-mono text-secondary uppercase tracking-wider truncate">
            Knovex Intelligence
          </span>
        )}
      </div>

      {/* Right — engine badge + theme toggle */}
      <div className="flex items-center space-x-3 shrink-0 ml-4">
        {/* Discrete engine badge */}
        <span className="hidden md:inline-flex items-center space-x-1.5 text-xs font-mono text-secondary border border-line bg-elevated/40 px-2 py-0.5 rounded-chip">
          <span className="w-1.5 h-1.5 rounded-chip bg-mark" />
          <span>Knovex RAG</span>
        </span>

        {/* Theme toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label="Toggle Theme"
          className="p-1.5 text-secondary hover:text-ink hover:bg-elevated rounded-button transition-colors"
        >
          {theme === 'dark' ? (
            <Sun size={15} strokeWidth={1.5} />
          ) : (
            <Moon size={15} strokeWidth={1.5} />
          )}
        </button>
      </div>
    </header>
  );
};
