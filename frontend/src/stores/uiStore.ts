import { create } from 'zustand';
import { RAGMode, Theme, TopK } from '../types.ts';

interface UIState {
  theme: Theme;
  topK: TopK;
  mode: RAGMode;
  inspectorOpen: boolean;
  toggleTheme: () => void;
  setTopK: (k: TopK) => void;
  setMode: (m: RAGMode) => void;
  setInspectorOpen: (open: boolean) => void;
}

const THEME_STORAGE_KEY = 'knovex_ui_theme';

function getInitialTheme(): Theme {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  const theme: Theme = (saved === 'dark' || saved === 'light') ? saved : 'light';
  // Apply class immediately on load so CSS vars are correct from the start
  if (theme === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
  return theme;
}

export const useUIStore = create<UIState>((set, get) => ({
  theme: getInitialTheme(),
  topK: 5,
  mode: 'rerank',
  inspectorOpen: false,

  toggleTheme: () => {
    const next = get().theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem(THEME_STORAGE_KEY, next);
    if (next === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    set({ theme: next });
  },

  setTopK: (topK) => set({ topK }),
  setMode: (mode) => set({ mode }),
  setInspectorOpen: (inspectorOpen) => set({ inspectorOpen }),
}));
