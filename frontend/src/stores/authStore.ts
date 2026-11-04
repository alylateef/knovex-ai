import { create } from 'zustand';
import { User } from '../types.ts';
import { apiGetMe, apiLogin, apiLogout, apiRegister, getAccessToken } from '../api.ts';
import { useThreadsStore } from './threadsStore.ts';
import { useDocsStore } from './docsStore.ts';
import { useCitationStore } from './citationStore.ts';

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  error: string | null;
  init: () => Promise<void>;
  login: (email: string, pass: string) => Promise<void>;
  register: (org: string, email: string, pass: string, name?: string, role?: 'admin' | 'user') => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: getAccessToken(),
  isLoading: true,
  error: null,

  init: async () => {
    const token = getAccessToken();
    if (!token) {
      set({ user: null, token: null, isLoading: false });
      return;
    }
    try {
      const user = await apiGetMe();
      set({ user, token, isLoading: false, error: null });
    } catch {
      set({ user: null, token: null, isLoading: false });
    }
  },

  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const res = await apiLogin({ email, password });
      const user = await apiGetMe();
      set({ user, token: res.access_token, isLoading: false, error: null });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Sign in failed';
      set({ isLoading: false, error: msg });
      throw err;
    }
  },

  register: async (organization_name, email, password, full_name, role = 'admin') => {
    set({ isLoading: true, error: null });
    try {
      const res = await apiRegister({ organization_name, email, password, full_name, role });
      const user = await apiGetMe();
      set({ user, token: res.access_token, isLoading: false, error: null });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Registration failed';
      set({ isLoading: false, error: msg });
      throw err;
    }
  },

  logout: async () => {
    set({ isLoading: true });
    try {
      await apiLogout();
    } finally {
      useThreadsStore.getState().reset();
      useDocsStore.getState().reset();
      useCitationStore.getState().clearCitation();
      set({ user: null, token: null, isLoading: false, error: null });
    }
  },

  clearError: () => set({ error: null }),
}));

// Global listener for session expiration or token revocation
if (typeof window !== 'undefined') {
  window.addEventListener('knovex:unauthorized', () => {
    useThreadsStore.getState().reset();
    useDocsStore.getState().reset();
    useCitationStore.getState().clearCitation();
    useAuthStore.setState({ user: null, token: null, isLoading: false });
  });
}
