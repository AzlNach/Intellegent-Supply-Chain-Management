import React, { useState } from 'react';
import { useOfficeStore } from '../store/useOfficeStore';
import type { AgentState, SolverState } from '../scene/types';

export const DebugPanel: React.FC = () => {
  const agentState = useOfficeStore((s) => s.agentState);
  const solverState = useOfficeStore((s) => s.solverState);
  const showSpeechBubble = useOfficeStore((s) => s.showSpeechBubble);

  const setAgentState = useOfficeStore((s) => s.setAgentState);
  const setSolverState = useOfficeStore((s) => s.setSolverState);
  const setChatMessage = useOfficeStore((s) => s.setChatMessage);
  const toggleSpeechBubble = useOfficeStore((s) => s.toggleSpeechBubble);
  const applyPreset = useOfficeStore((s) => s.applyPreset);
  const updateBoardField = useOfficeStore((s) => s.updateBoardField);

  const [customMsg, setCustomMsg] = useState('');
  const [collapsed, setCollapsed] = useState(false);

  const agentStates: { id: AgentState; label: string; desc: string }[] = [
    { id: 'idle', label: 'Idle', desc: 'Duduk & ketik santai' },
    { id: 'reading_board', label: 'Reading Board', desc: 'Jalan ke papan tulis' },
    { id: 'working', label: 'Working', desc: 'Ketik cepat aktif' },
    { id: 'waiting', label: 'Waiting', desc: 'Duduk + ikon ⏳' },
    { id: 'reporting', label: 'Reporting', desc: 'Jalan ke meja Head' },
  ];

  const solverStates: { id: SolverState; label: string; color: string }[] = [
    { id: 'idle', label: 'Idle (Standby)', color: '#38bdf8' },
    { id: 'working', label: 'Working (Pulsing)', color: '#f59e0b' },
    { id: 'done', label: 'Done (Ready)', color: '#10b981' },
  ];

  return (
    <div
      style={{
        position: 'absolute',
        top: '16px',
        right: '16px',
        width: collapsed ? 'auto' : '340px',
        maxHeight: 'calc(100vh - 32px)',
        overflowY: 'auto',
        background: 'rgba(15, 23, 42, 0.92)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(56, 189, 248, 0.25)',
        borderRadius: '12px',
        color: '#f8fafc',
        padding: collapsed ? '8px 12px' : '16px',
        boxShadow: '0 12px 32px rgba(0, 0, 0, 0.6)',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        zIndex: 50,
        userSelect: 'none',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: collapsed ? '0' : '14px',
          borderBottom: collapsed ? 'none' : '1px solid #334155',
          paddingBottom: collapsed ? '0' : '10px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              background: '#38bdf8',
              boxShadow: '0 0 8px #38bdf8',
            }}
          />
          <span style={{ fontWeight: 'bold', fontSize: '13px', letterSpacing: '0.5px' }}>
            OFFICE 3D DEBUG PANEL
          </span>
        </div>
        <button
          onClick={() => setCollapsed(!collapsed)}
          style={{
            background: '#1e293b',
            border: '1px solid #475569',
            color: '#94a3b8',
            borderRadius: '6px',
            padding: '3px 8px',
            fontSize: '11px',
            cursor: 'pointer',
          }}
        >
          {collapsed ? 'Buka' : 'Tutup'}
        </button>
      </div>

      {!collapsed && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Quick Scenario Presets */}
          <div>
            <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#94a3b8', marginBottom: '6px' }}>
              SKENARIO PRESET CEPAT
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
              <button
                onClick={() => applyPreset('initial')}
                style={btnStyle}
              >
                1. Data Awal (Kosong)
              </button>
              <button
                onClick={() => applyPreset('conflict')}
                style={{ ...btnStyle, borderColor: '#ef4444', color: '#fca5a5' }}
              >
                2. Deteksi Konflik
              </button>
              <button
                onClick={() => applyPreset('ready_for_solver')}
                style={{ ...btnStyle, borderColor: '#f59e0b', color: '#fde68a' }}
              >
                3. Kirim ke Solver
              </button>
              <button
                onClick={() => applyPreset('solved')}
                style={{ ...btnStyle, borderColor: '#10b981', color: '#6ee7b7' }}
              >
                4. Solver Selesai
              </button>
            </div>
          </div>

          {/* 1. AGENT STATE */}
          <div>
            <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#94a3b8', marginBottom: '6px' }}>
              1. AGENT_STATE ({agentState.toUpperCase()})
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {agentStates.map((st) => {
                const isActive = agentState === st.id;
                return (
                  <button
                    key={st.id}
                    onClick={() => setAgentState(st.id)}
                    style={{
                      ...btnStyle,
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      background: isActive ? '#0369a1' : '#1e293b',
                      borderColor: isActive ? '#38bdf8' : '#334155',
                      color: isActive ? '#ffffff' : '#cbd5e1',
                    }}
                  >
                    <span>{st.label}</span>
                    <span style={{ fontSize: '10px', color: isActive ? '#bae6fd' : '#64748b' }}>
                      {st.desc}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 2. SOLVER STATE */}
          <div>
            <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#94a3b8', marginBottom: '6px' }}>
              2. SOLVER_STATE ({solverState.toUpperCase()})
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px' }}>
              {solverStates.map((st) => {
                const isActive = solverState === st.id;
                return (
                  <button
                    key={st.id}
                    onClick={() => setSolverState(st.id)}
                    style={{
                      ...btnStyle,
                      background: isActive ? '#1e293b' : '#0f172a',
                      borderColor: isActive ? st.color : '#334155',
                      color: isActive ? st.color : '#94a3b8',
                      fontWeight: isActive ? 'bold' : 'normal',
                      boxShadow: isActive ? `0 0 8px ${st.color}55` : 'none',
                    }}
                  >
                    {st.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 3. WHITEBOARD DATA TOGGLE */}
          <div>
            <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#94a3b8', marginBottom: '6px' }}>
              3. BOARD_UPDATE (UBAH STATUS FIELD)
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
              <button
                onClick={() =>
                  updateBoardField('on_hand_qty', {
                    value: 25,
                    status: 'defined',
                    source: 'audit_fisik',
                  })
                }
                style={{ ...btnStyle, fontSize: '11px' }}
              >
                On Hand: Defined (25)
              </button>
              <button
                onClick={() =>
                  updateBoardField('on_hand_qty', {
                    value: '10 vs 25',
                    status: 'conflict',
                    source: 'user_vs_db',
                  })
                }
                style={{ ...btnStyle, fontSize: '11px', color: '#f87171' }}
              >
                On Hand: Conflict
              </button>
              <button
                onClick={() =>
                  updateBoardField('expected_outgoing_qty', {
                    value: null,
                    status: 'undefined',
                    source: 'belum_ditentukan',
                  })
                }
                style={{ ...btnStyle, fontSize: '11px' }}
              >
                Outgoing: Undefined
              </button>
              <button
                onClick={() =>
                  updateBoardField('expected_outgoing_qty', {
                    value: 12,
                    status: 'defined',
                    source: 'sop_demand',
                  })
                }
                style={{ ...btnStyle, fontSize: '11px', color: '#34d399' }}
              >
                Outgoing: Defined (12)
              </button>
            </div>
          </div>

          {/* 4. CHAT MESSAGE & SPEECH BUBBLE */}
          <div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '6px',
              }}
            >
              <span style={{ fontSize: '11px', fontWeight: 'bold', color: '#94a3b8' }}>
                4. CHAT_MESSAGE (SPEECH BUBBLE)
              </span>
              <button
                onClick={() => toggleSpeechBubble()}
                style={{
                  background: 'none',
                  border: 'none',
                  color: showSpeechBubble ? '#38bdf8' : '#64748b',
                  fontSize: '11px',
                  cursor: 'pointer',
                  textDecoration: 'underline',
                }}
              >
                {showSpeechBubble ? 'Sembunyikan' : 'Tampilkan'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: '6px', marginBottom: '6px' }}>
              <input
                type="text"
                value={customMsg}
                onChange={(e) => setCustomMsg(e.target.value)}
                placeholder="Ketik pesan balon ucapan..."
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
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && customMsg.trim()) {
                    setChatMessage(customMsg.trim());
                    setCustomMsg('');
                  }
                }}
              />
              <button
                onClick={() => {
                  if (customMsg.trim()) {
                    setChatMessage(customMsg.trim());
                    setCustomMsg('');
                  }
                }}
                style={{ ...btnStyle, width: 'auto', padding: '6px 12px' }}
              >
                Kirim
              </button>
            </div>
            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
              {[
                'Cek data fisik Mie A',
                'Ada konflik stok!',
                'Kalkulator siap',
                'Kekurangan: 22 bungkus',
              ].map((msg, i) => (
                <button
                  key={i}
                  onClick={() => setChatMessage(msg)}
                  style={{
                    background: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: '4px',
                    color: '#94a3b8',
                    fontSize: '10px',
                    padding: '3px 6px',
                    cursor: 'pointer',
                  }}
                >
                  "{msg}"
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const btnStyle: React.CSSProperties = {
  background: '#1e293b',
  border: '1px solid #334155',
  borderRadius: '6px',
  color: '#e2e8f0',
  padding: '6px 10px',
  fontSize: '12px',
  cursor: 'pointer',
  textAlign: 'center',
  transition: 'all 0.15s ease',
};
