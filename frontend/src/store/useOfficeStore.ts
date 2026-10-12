import { create } from 'zustand';
import type { AgentState, BoardData, OfficeSceneState, SolverState } from '../scene/types';

export const INITIAL_BOARD_DATA: BoardData = {
  division: 'SCDS-OR (Supply Chain & Operations Research)',
  title: 'Inventory Gap Status Board',
  lastUpdated: new Date().toLocaleTimeString(),
  fields: {
    product_id: {
      key: 'product_id',
      label: 'Product ID',
      value: 'MIE-A',
      status: 'defined',
      source: 'catalog_db',
    },
    on_hand_qty: {
      key: 'on_hand_qty',
      label: 'On Hand Qty',
      value: 25,
      status: 'defined',
      source: 'audit_fisik',
    },
    target_qty: {
      key: 'target_qty',
      label: 'Target Qty',
      value: 50,
      status: 'defined',
      source: 'sop_policy',
    },
    expected_outgoing_qty: {
      key: 'expected_outgoing_qty',
      label: 'Expected Outgoing Qty',
      value: 12,
      status: 'defined',
      source: 'user_claim',
    },
    required_by: {
      key: 'required_by',
      label: 'Required By',
      value: '2026-10-15 18:00',
      status: 'defined',
      source: 'order_deadline',
    },
  },
};

interface OfficeStoreActions {
  mode: 'mock' | 'live';
  setMode: (mode: 'mock' | 'live') => void;
  setAgentState: (state: AgentState) => void;
  setSolverState: (state: SolverState) => void;
  setBoardData: (data: Partial<BoardData>) => void;
  updateBoardField: (
    fieldKey: keyof BoardData['fields'],
    patch: Partial<BoardData['fields'][keyof BoardData['fields']]>
  ) => void;
  setChatMessage: (msg: string | null) => void;
  toggleSpeechBubble: (show?: boolean) => void;
  applyPreset: (preset: 'initial' | 'conflict' | 'ready_for_solver' | 'solved') => void;
}

export type OfficeStore = OfficeSceneState & OfficeStoreActions;

export const useOfficeStore = create<OfficeStore>((set) => ({
  mode: 'mock',
  agentState: 'idle',
  solverState: 'idle',
  boardData: INITIAL_BOARD_DATA,
  latestChatMessage: 'Halo! Saya IE Agent divisi SCDS-OR. Ada stok yang perlu dianalisis?',
  showSpeechBubble: true,

  setMode: (mode) => set({ mode }),
  setAgentState: (state) => set({ agentState: state }),
  setSolverState: (state) => set({ solverState: state }),
  setBoardData: (data) =>
    set((s) => ({
      boardData: {
        ...s.boardData,
        ...data,
        lastUpdated: new Date().toLocaleTimeString(),
      },
    })),

  updateBoardField: (fieldKey, patch) =>
    set((s) => {
      const currentFields = s.boardData.fields;
      return {
        boardData: {
          ...s.boardData,
          lastUpdated: new Date().toLocaleTimeString(),
          fields: {
            ...currentFields,
            [fieldKey]: {
              ...currentFields[fieldKey],
              ...patch,
            },
          },
        },
      };
    }),

  setChatMessage: (msg) => set({ latestChatMessage: msg, showSpeechBubble: !!msg }),
  toggleSpeechBubble: (show) =>
    set((s) => ({ showSpeechBubble: show ?? !s.showSpeechBubble })),

  applyPreset: (preset) => {
    switch (preset) {
      case 'initial':
        set({
          agentState: 'idle',
          solverState: 'idle',
          latestChatMessage: 'Selamat datang. Menunggu instruksi pengecekan data stok.',
          boardData: {
            ...INITIAL_BOARD_DATA,
            fields: {
              ...INITIAL_BOARD_DATA.fields,
              on_hand_qty: {
                key: 'on_hand_qty',
                label: 'On Hand Qty',
                value: null,
                status: 'undefined',
                source: 'belum_verifikasi',
              },
              expected_outgoing_qty: {
                key: 'expected_outgoing_qty',
                label: 'Expected Outgoing Qty',
                value: null,
                status: 'undefined',
                source: 'belum_ditentukan',
              },
            },
          },
        });
        break;

      case 'conflict':
        set({
          agentState: 'reading_board',
          solverState: 'idle',
          latestChatMessage:
            'Perhatian: Ditemukan konflik stok fisik (10) vs sistem (25). Perlu klarifikasi user.',
          boardData: {
            ...INITIAL_BOARD_DATA,
            fields: {
              ...INITIAL_BOARD_DATA.fields,
              on_hand_qty: {
                key: 'on_hand_qty',
                label: 'On Hand Qty',
                value: '10 vs 25',
                status: 'conflict',
                source: 'discrepancy_flag',
              },
            },
          },
        });
        break;

      case 'ready_for_solver':
        set({
          agentState: 'working',
          solverState: 'working',
          latestChatMessage:
            'Semua parameter terverifikasi. Mengirim task ke solver engine...',
          boardData: INITIAL_BOARD_DATA,
        });
        break;

      case 'solved':
        set({
          agentState: 'reporting',
          solverState: 'done',
          latestChatMessage:
            'Solver selesai: Projected balance = 28, Shortfall = 22 unit. Siap dilaporkan ke Head.',
          boardData: INITIAL_BOARD_DATA,
        });
        break;
    }
  },
}));
