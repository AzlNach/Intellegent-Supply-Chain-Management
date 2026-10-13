import { create } from 'zustand';

export interface LiveMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export interface Proposal {
  update_id: string;
  product_id: string;
  status: string;
  source_ref?: string;
  old_values?: unknown;
  new_values?: unknown;
}

export interface LiveEvent {
  id: string;
  type: string;
  at: number;
  payload: unknown;
}

interface LiveStore {
  connected: boolean;
  messages: LiveMessage[];
  proposals: Proposal[];
  events: LiveEvent[];
  setConnected: (connected: boolean) => void;
  pushMessage: (message: LiveMessage) => void;
  pushProposal: (proposal: Proposal) => void;
  updateProposalStatus: (updateId: string, status: string) => void;
  pushEvent: (type: string, payload: unknown) => void;
  reset: () => void;
}

const MAX_EVENTS = 50;

let counter = 0;
const nextId = (prefix: string) => `${prefix}-${Date.now()}-${counter++}`;

export const useLiveStore = create<LiveStore>((set) => ({
  connected: false,
  messages: [],
  proposals: [],
  events: [],

  setConnected: (connected) => set({ connected }),

  pushMessage: (message) =>
    set((s) => {
      const duplicate = s.messages.some(
        (existing) =>
          existing.role === message.role &&
          existing.content === message.content
      );
      return duplicate ? s : { messages: [...s.messages, message] };
    }),

  pushProposal: (proposal) =>
    set((s) => ({
      proposals: [
        ...s.proposals.filter((p) => p.update_id !== proposal.update_id),
        proposal,
      ],
    })),

  updateProposalStatus: (updateId, status) =>
    set((s) => ({
      proposals: s.proposals.map((p) =>
        p.update_id === updateId ? { ...p, status } : p
      ),
    })),

  pushEvent: (type, payload) =>
    set((s) => {
      const event: LiveEvent = { id: nextId('evt'), type, at: Date.now(), payload };
      return { events: [...s.events, event].slice(-MAX_EVENTS) };
    }),

  reset: () => set({ messages: [], proposals: [], events: [] }),
}));
