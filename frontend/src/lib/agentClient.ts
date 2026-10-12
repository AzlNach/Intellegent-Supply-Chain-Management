const BASE =
  (import.meta.env.VITE_AGENT_URL as string | undefined) ?? 'http://127.0.0.1:8000';

export const AGENT_HTTP_URL = BASE.replace(/\/$/, '');
export const AGENT_WS_URL = `${AGENT_HTTP_URL.replace(/^http/, 'ws')}/ws`;

export function getSessionId(): string {
  const key = 'vo_session_id';
  let id = localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(key, id);
  }
  return id;
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${AGENT_HTTP_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function postChat(sessionId: string, message: string) {
  return postJson('/chat', { session_id: sessionId, message });
}

export function confirmProposal(updateId: string) {
  return postJson(`/proposals/${updateId}/confirm`);
}

export function rejectProposal(updateId: string) {
  return postJson(`/proposals/${updateId}/reject`);
}
