import React, { useRef, useState } from 'react';
import { getSessionId, postChat, confirmProposal, rejectProposal } from '../lib/agentClient';
import { useAgentSocket } from '../lib/useAgentSocket';
import { useLiveStore } from '../store/useLiveStore';
import { useOfficeStore } from '../store/useOfficeStore';

const panelStyle: React.CSSProperties = {
  position: 'absolute',
  top: '16px',
  right: '16px',
  width: 'min(360px, calc(100vw - 32px))',
  maxHeight: 'calc(100vh - 32px)',
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
  background: 'rgba(15, 23, 42, 0.92)',
  backdropFilter: 'blur(12px)',
  border: '1px solid rgba(56, 189, 248, 0.25)',
  borderRadius: '12px',
  color: '#f8fafc',
  padding: '16px',
  boxShadow: '0 12px 32px rgba(0, 0, 0, 0.6)',
  fontFamily: 'system-ui, -apple-system, sans-serif',
  zIndex: 50,
  overflow: 'hidden',
};

const btnStyle: React.CSSProperties = {
  background: '#1e293b',
  border: '1px solid #475569',
  borderRadius: '6px',
  color: '#e2e8f0',
  padding: '6px 10px',
  fontSize: '12px',
  cursor: 'pointer',
};

export const LivePanel: React.FC = () => {
  const sessionId = React.useMemo(() => getSessionId(), []);
  useAgentSocket(true, sessionId);

  const connected = useLiveStore((s) => s.connected);
  const messages = useLiveStore((s) => s.messages);
  const proposals = useLiveStore((s) => s.proposals);
  const events = useLiveStore((s) => s.events);
  const updateProposalStatus = useLiveStore((s) => s.updateProposalStatus);

  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const actionLock = useRef(false);

  const runOnce = async (action: () => Promise<void>) => {
    if (actionLock.current) return;
    actionLock.current = true;
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      actionLock.current = false;
      setBusy(false);
    }
  };

  const send = () => {
    const text = draft.trim();
    if (!text || actionLock.current) return;
    setDraft('');
    void runOnce(async () => {
      useLiveStore.getState().pushMessage({ id: `${Date.now()}-u`, role: 'user', content: text });
      const response = await postChat(sessionId, text) as { message_to_user?: string };
      if (response.message_to_user) {
        const current = useLiveStore.getState().messages;
        if (current.at(-1)?.content !== response.message_to_user) {
          useLiveStore.getState().pushMessage({
            id: `${Date.now()}-a-http`,
            role: 'assistant',
            content: response.message_to_user,
          });
        }
        useOfficeStore.getState().setChatMessage(response.message_to_user);
      }
    });
  };

  const confirm = (updateId: string) => {
    void runOnce(async () => {
      await confirmProposal(updateId);
      updateProposalStatus(updateId, 'APPROVED');
    });
  };

  const reject = (updateId: string) => {
    void runOnce(async () => {
      await rejectProposal(updateId);
      updateProposalStatus(updateId, 'REJECTED');
    });
  };

  return (
    <div style={panelStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div
          style={{
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            background: connected ? '#10b981' : '#ef4444',
            boxShadow: connected ? '0 0 8px #10b981' : '0 0 8px #ef4444',
          }}
        />
        <span style={{ fontWeight: 'bold', fontSize: '13px' }}>IE AGENT — LIVE</span>
        <span style={{ marginLeft: 'auto', fontSize: '11px', color: connected ? '#6ee7b7' : '#fca5a5' }}>
          {connected ? 'Terhubung' : 'Terputus'}
        </span>
      </div>

      {/* Chat history */}
      <div
        style={{
          flex: 1,
          minHeight: '160px',
          maxHeight: '220px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
        }}
      >
        {messages.length === 0 && (
          <div style={{ fontSize: '12px', color: '#64748b' }}>
            Kirim pesan untuk memulai percakapan dengan IE Agent.
          </div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            style={{
              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
              background: m.role === 'user' ? '#0369a1' : '#1e293b',
              border: '1px solid #334155',
              borderRadius: '8px',
              padding: '6px 10px',
              maxWidth: '85%',
              fontSize: '12px',
              lineHeight: 1.4,
            }}
          >
            {m.content}
          </div>
        ))}
      </div>

      {/* Composer */}
      <div style={{ display: 'flex', gap: '6px' }}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          disabled={busy}
          placeholder="Tulis pesan untuk IE Agent..."
          style={{
            flex: 1,
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '6px',
            color: '#f8fafc',
            padding: '6px 10px',
            fontSize: '12px',
            outline: 'none',
          }}
        />
        <button onClick={send} disabled={busy} style={btnStyle}>
          {busy ? '...' : 'Kirim'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {['Cek stok MIE-A', 'Hitung kebutuhan stok', 'Perbarui data stok'].map((suggestion) => (
          <button key={suggestion} disabled={busy} style={{ ...btnStyle, padding: '4px 7px', fontSize: 10 }} onClick={() => setDraft(suggestion)}>
            {suggestion}
          </button>
        ))}
      </div>

      {error && (
        <div style={{ fontSize: '11px', color: '#fca5a5' }}>Error: {error}</div>
      )}

      {/* Proposals */}
      {proposals.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#94a3b8' }}>
            USULAN PERUBAHAN ({proposals.length})
          </div>
          {proposals.map((p) => (
            <div
              key={p.update_id}
              style={{
                background: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '8px',
                padding: '8px 10px',
                fontSize: '11px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px' }}>
                <span style={{ color: '#cbd5e1' }}>{p.product_id || p.update_id}</span>
                <span
                  style={{
                    color: p.status === 'APPROVED' ? '#6ee7b7' : p.status === 'REJECTED' ? '#fca5a5' : '#fde68a',
                  }}
                >
                  {p.status}
                </span>
              </div>
              {p.status === 'PENDING' && (
                <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                  <button onClick={() => confirm(p.update_id)} disabled={busy} style={btnStyle}>
                    Setuju
                  </button>
                  <button onClick={() => reject(p.update_id)} disabled={busy} style={btnStyle}>
                    Tolak
                  </button>
                </div>
              )}
              {Boolean(p.old_values || p.new_values) && (
                <pre style={{ whiteSpace: 'pre-wrap', marginTop: 6, color: '#cbd5e1', fontSize: 10 }}>
                  {JSON.stringify({ old: p.old_values, new: p.new_values }, null, 1)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Event log (last 50) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#94a3b8' }}>
          EVENT LOG ({events.length})
        </div>
        <div style={{ maxHeight: '120px', overflowY: 'auto', fontSize: '10px', color: '#94a3b8' }}>
          {events.map((e) => (
            <div key={e.id} style={{ fontFamily: 'monospace' }}>
              {new Date(e.at).toLocaleTimeString()} · {e.type}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
