import React from 'react';
import { OfficeScene } from './scene/OfficeScene';
import { DebugPanel } from './components/DebugPanel';
import { LivePanel } from './components/LivePanel';
import { useOfficeStore } from './store/useOfficeStore';

export const App: React.FC = () => {
  const agentState = useOfficeStore((s) => s.agentState);
  const solverState = useOfficeStore((s) => s.solverState);
  const lastUpdated = useOfficeStore((s) => s.boardData.lastUpdated);
  const mode = useOfficeStore((s) => s.mode);
  const setMode = useOfficeStore((s) => s.setMode);

  return (
    <div style={{ width: '100vw', height: '100vh', position: 'relative', overflow: 'hidden' }}>
      {/* Top Left Division Header Overlay */}
      <div
        style={{
          position: 'absolute',
          top: '16px',
          left: '16px',
          zIndex: 40,
          background: 'rgba(15, 23, 42, 0.9)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(56, 189, 248, 0.25)',
          borderRadius: '12px',
          padding: '12px 18px',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)',
          userSelect: 'none',
          pointerEvents: 'auto',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <span style={{ fontSize: '15px', fontWeight: 800, color: '#38bdf8', letterSpacing: '0.8px' }}>
            DIVISI SCDS-OR
          </span>
          <span
            style={{
              fontSize: '10px',
              background: '#1e293b',
              color: '#94a3b8',
              padding: '2px 6px',
              borderRadius: '4px',
              fontWeight: 600,
            }}
          >
            ISOMETRIC PIXEL ART OFFICE
          </span>
        </div>
        <div style={{ fontSize: '11px', color: '#94a3b8' }}>
          Supply Chain & Operations Research • Stock Memory Copilot
        </div>

        {/* Mode switch and scene status */}
        <div style={{ display: 'flex', gap: '14px', marginTop: '10px', paddingTop: '8px', borderTop: '1px solid #334155', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '11px', color: '#64748b' }}>Mode:</span>
              <button
                onClick={() => setMode(mode === 'mock' ? 'live' : 'mock')}
                style={{
                  background: mode === 'live' ? '#0369a1' : '#1e293b',
                  border: '1px solid #38bdf8',
                  color: mode === 'live' ? '#ffffff' : '#94a3b8',
                  borderRadius: '999px',
                  padding: '2px 10px',
                  fontSize: '11px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                }}
              >
                {mode === 'live' ? 'LIVE' : 'MOCK'}
              </button>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '11px', color: '#64748b' }}>Agent:</span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 'bold',
                color: agentState === 'working' ? '#f59e0b' : agentState === 'reading_board' ? '#38bdf8' : '#34d399',
              }}
            >
              {agentState.toUpperCase()}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '11px', color: '#64748b' }}>Solver:</span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 'bold',
                color: solverState === 'working' ? '#f59e0b' : solverState === 'done' ? '#10b981' : '#38bdf8',
              }}
            >
              {solverState.toUpperCase()}
            </span>
          </div>

          <div style={{ fontSize: '10px', color: '#64748b', alignSelf: 'center' }}>
            Sync: {lastUpdated}
          </div>
        </div>
      </div>

      {mode === 'mock' && <div
        style={{
          position: 'absolute',
          bottom: '16px',
          left: '16px',
          zIndex: 40,
          background: 'rgba(15, 23, 42, 0.8)',
          backdropFilter: 'blur(8px)',
          border: '1px solid #334155',
          borderRadius: '8px',
          padding: '6px 12px',
          fontSize: '11px',
          color: '#94a3b8',
          userSelect: 'none',
          pointerEvents: 'none',
        }}
      >
        🖱️ Geser: Klik & seret • Zoom: Scroll mouse / Tombol +/- • Klik objek interaktif untuk inspeksi
      </div>}

      {/* Isometric Scene (Purely Presentational, Zero Network Calls Inside) */}
      <OfficeScene />

      {/* Mock presets are local-only; live mode uses the agent-service. */}
      {mode === 'mock' ? <DebugPanel /> : <LivePanel />}
    </div>
  );
};

export default App;
