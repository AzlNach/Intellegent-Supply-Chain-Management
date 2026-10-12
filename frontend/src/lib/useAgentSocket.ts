import { useEffect } from 'react';
import { AGENT_WS_URL } from './agentClient';
import { useLiveStore } from '../store/useLiveStore';
import { useOfficeStore } from '../store/useOfficeStore';
import type { AgentState, BoardData, ParamStatus, SolverState } from '../scene/types';

type BackendParameter = { value: unknown; status: string; source: string };

const AGENT_STATES: AgentState[] = [
  'idle',
  'reading_board',
  'working',
  'waiting',
  'reporting',
];

function toAgentState(state: string): AgentState {
  switch (state) {
    case 'thinking':
    case 'calling_tool':
      return 'working';
    case 'done':
      return 'idle';
    default:
      return AGENT_STATES.includes(state as AgentState) ? (state as AgentState) : 'idle';
  }
}

function toParamStatus(status: string): ParamStatus {
  if (status === 'VERIFIED') return 'defined';
  if (status === 'CONFLICT') return 'conflict';
  return 'undefined';
}

function toBoardValue(value: unknown): string | number | null {
  if (typeof value === 'string' || typeof value === 'number') return value;
  return null;
}

function boardFromParameters(parameters: Record<string, BackendParameter>): BoardData {
  const fieldKeys = [
    'product_id',
    'on_hand_qty',
    'target_qty',
    'expected_outgoing_qty',
    'required_by',
  ] as const;

  const fields = {} as BoardData['fields'];
  for (const key of fieldKeys) {
    const entry = parameters[key] as BackendParameter | undefined;
    fields[key] = {
      key,
      label: key,
      value: toBoardValue(entry?.value),
      status: entry ? toParamStatus(entry.status) : 'undefined',
      source: entry?.source ?? 'unknown',
    };
  }

  return {
    division: 'SCDS-OR',
    title: 'Inventory Gap Status Board',
    lastUpdated: new Date().toLocaleTimeString(),
    fields,
  };
}

export function useAgentSocket(enabled: boolean, sessionId: string): void {
  useEffect(() => {
    if (!enabled) return;

    let socket: WebSocket | null = null;
    let closed = false;
    let retryTimer: number | undefined;

    const connect = () => {
      if (closed) return;
      socket = new WebSocket(`${AGENT_WS_URL}/${sessionId}`);

      socket.onopen = () => {
        useLiveStore.getState().setConnected(true);
      };

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data as string) as {
            type: string;
            state?: string;
            role?: string;
            content?: string;
            board?: { parameters?: Record<string, BackendParameter> };
            proposal?: Record<string, unknown>;
            message?: string;
            parameters?: Record<string, BackendParameter>;
            messages?: Array<{ role: string; content: string }>;
          };
          const live = useLiveStore.getState();
          const office = useOfficeStore.getState();
          live.pushEvent(msg.type, msg);

          switch (msg.type) {
            case 'session_snapshot':
              if (msg.parameters) office.setBoardData(boardFromParameters(msg.parameters));
              for (const item of msg.messages ?? []) {
                if (item.role === 'user' || item.role === 'assistant') {
                  live.pushMessage({
                    id: `snapshot-${Date.now()}-${Math.random()}`,
                    role: item.role,
                    content: item.content,
                  });
                }
              }
              break;
            case 'agent_state':
              if (msg.state) office.setAgentState(toAgentState(msg.state));
              break;
            case 'solver_state':
              if (msg.state) office.setSolverState(msg.state as SolverState);
              break;
            case 'chat_message':
              if (msg.content) {
                live.pushMessage({
                  id: `${Date.now()}-${Math.random()}`,
                  role: (msg.role === 'user' ? 'user' : 'assistant'),
                  content: msg.content,
                });
                office.setChatMessage(msg.content);
              }
              break;
            case 'board_update':
              if (msg.board?.parameters) {
                office.setBoardData(boardFromParameters(msg.board.parameters));
              }
              break;
            case 'proposal_created':
              if (msg.proposal?.update_id) {
                live.pushProposal({
                  update_id: String(msg.proposal.update_id),
                  product_id: String(msg.proposal.product_id ?? ''),
                  status: String(msg.proposal.status ?? 'PENDING'),
                  source_ref: msg.proposal.source_ref as string | undefined,
                  old_values: msg.proposal.old_values,
                  new_values: msg.proposal.new_values,
                });
              }
              break;
            case 'error':
              // surfaced via event log; no scene mutation
              break;
          }
        } catch {
          /* ignore malformed frame */
        }
      };

      socket.onclose = () => {
        useLiveStore.getState().setConnected(false);
        socket = null;
        if (!closed) {
          retryTimer = window.setTimeout(connect, 2000);
        }
      };

      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();
    return () => {
      closed = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      socket?.close();
      useLiveStore.getState().setConnected(false);
    };
  }, [enabled, sessionId]);
}
