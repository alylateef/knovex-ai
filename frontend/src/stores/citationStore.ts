import { create } from 'zustand';
import { SourceChunk } from '../types.ts';

interface CitationState {
  activeChunk: SourceChunk | null;
  activeClaim: string | null;
  activeNumber: number | null;
  selectCitation: (chunk: SourceChunk, claimText: string, number: number) => void;
  clearCitation: () => void;
}

export const useCitationStore = create<CitationState>((set) => ({
  activeChunk: null,
  activeClaim: null,
  activeNumber: null,

  selectCitation: (activeChunk, activeClaim, activeNumber) =>
    set({ activeChunk, activeClaim, activeNumber }),

  clearCitation: () =>
    set({ activeChunk: null, activeClaim: null, activeNumber: null }),
}));
