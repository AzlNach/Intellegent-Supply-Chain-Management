import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Application, extend, useApplication, useTick } from '@pixi/react';
import { Container, Graphics, Sprite, Text, Texture } from 'pixi.js';
import { useOfficeStore } from '../store/useOfficeStore';
import type { OfficeSceneProps } from './types';
import {
  createOfficeSceneTexture,
  drawOfficeFrame,
  OFFICE_HEIGHT,
  OFFICE_WIDTH,
  type AgentMotion,
} from './htmlOfficeRenderer';

extend({ Container, Graphics, Sprite, Text });

const FRAME_WIDTH = 960;
const FRAME_HEIGHT = 540;
const DESIGN_SCALE_X = FRAME_WIDTH / OFFICE_WIDTH;
const DESIGN_SCALE_Y = FRAME_HEIGHT / OFFICE_HEIGHT;

interface OfficeRendererProps {
  onSelect?: (objectId: string) => void;
}

declare global {
  interface Window {
    __VO_DEV__?: {
      getState: () => Record<string, unknown>;
    getCanvasMetrics: () => Record<string, unknown>;
    pauseTicker: () => void;
    resumeTicker: () => void;
    };
  }
}

/** Pixi render loop; draws the original 352x196 office design into one nearest-neighbor texture. */
const OfficeRenderer: React.FC<OfficeRendererProps> = ({ onSelect }) => {
  const { app } = useApplication();
  const agentState = useOfficeStore((s) => s.agentState);
  const solverState = useOfficeStore((s) => s.solverState);
  const boardData = useOfficeStore((s) => s.boardData);
  const chatMessage = useOfficeStore((s) => s.latestChatMessage);
  const sceneRef = useRef<ReturnType<typeof createOfficeSceneTexture> | null>(null);
  const spriteRef = useRef<Sprite | null>(null);
  const chatUntilRef = useRef(0);
  const previousMessageRef = useRef<string | null>(chatMessage);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const motionRef = useRef<AgentMotion>({
    x: 3.17,
    y: 4.7,
    z: 4.2,
    facing: 'back',
    walking: false,
    typingPhase: 0,
    seated: true,
    waiting: false,
  });
  const pathRef = useRef<Array<{ x: number; y: number; z: number; facing: AgentMotion['facing'] }>>([]);
  const stateStartedRef = useRef(performance.now());
  const frameCounterRef = useRef({ start: performance.now(), frames: 0, fps: 0 });

  if (!sceneRef.current && typeof document !== 'undefined') {
    sceneRef.current = createOfficeSceneTexture();
  }

  useEffect(() => {
    if (chatMessage && chatMessage !== previousMessageRef.current) {
      chatUntilRef.current = performance.now() + 5000;
    }
    previousMessageRef.current = chatMessage;
  }, [chatMessage]);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    const getBubbleText = () => chatMessage && performance.now() < chatUntilRef.current
      ? chatMessage.length > 34 ? `${chatMessage.slice(0, 32)}…` : chatMessage
      : ({ idle: 'Menunggu tugas', reading_board: 'Membaca papan', working: 'Memproses data', waiting: 'Menunggu jawaban Anda', reporting: 'Melapor' } as const)[agentState];
    window.__VO_DEV__ = {
      getState: () => ({
        agentState,
        bubbleText: getBubbleText(),
        boardData: useOfficeStore.getState().boardData,
        solverState,
        character: { ...motionRef.current },
      }),
      getCanvasMetrics: () => {
        const canvas = app?.canvas;
        const source = sceneRef.current?.texture.source;
        return {
          backingWidth: canvas?.width ?? 0,
          backingHeight: canvas?.height ?? 0,
          displayWidth: canvas?.clientWidth ?? 0,
          displayHeight: canvas?.clientHeight ?? 0,
          sourceWidth: source?.width ?? 0,
          sourceHeight: source?.height ?? 0,
          scaleMode: source?.scaleMode ?? 'unknown',
          tickerStarted: app?.ticker.started ?? false,
          averageFps: frameCounterRef.current.fps,
        };
      },
      pauseTicker: () => app?.ticker.stop(),
      resumeTicker: () => app?.ticker.start(),
    };
    return () => {
      delete window.__VO_DEV__;
    };
  }, [app, agentState, solverState, boardData, chatMessage]);

  useEffect(() => {
    stateStartedRef.current = performance.now();
    const current = motionRef.current;
    const toDesk = [
      { x: 4.0, y: 5.2, z: 3.5, facing: 'back' as const },
      { x: 3.17, y: 4.7, z: 4.2, facing: 'back' as const },
    ];
    if (agentState === 'reading_board') {
      pathRef.current = [
        { x: 4.0, y: 4.0, z: 3.8, facing: 'left' },
        { x: 5.1, y: 2.5, z: 3.5, facing: 'left' },
        { x: 5.5, y: 0.85, z: 4.0, facing: 'back' },
      ];
      current.typingPhase = 0;
      current.seated = false;
      current.waiting = false;
    } else if (agentState === 'reporting') {
      pathRef.current = [
        { x: 4.0, y: 5.2, z: 3.5, facing: 'back' },
        { x: 6.0, y: 5.0, z: 3.5, facing: 'right' },
        { x: 8.7, y: 4.1, z: 4.0, facing: 'left' },
      ];
      current.typingPhase = 0;
      current.seated = false;
      current.waiting = false;
    } else {
      const awayFromDesk = Math.abs(current.x - 3.17) > 0.2 || Math.abs(current.y - 4.7) > 0.2;
      pathRef.current = awayFromDesk ? toDesk : [];
      current.typingPhase = 0;
      current.seated = agentState === 'idle' || agentState === 'working' || agentState === 'waiting';
      current.waiting = agentState === 'waiting';
      if (!awayFromDesk) {
        current.x = 3.17;
        current.y = 4.7;
        current.z = 4.2;
        current.facing = 'back';
        current.walking = false;
      }
    }
  }, [agentState]);

  useEffect(() => {
    if (!app || !sceneRef.current || !spriteRef.current) return;
    const interactiveSprite = spriteRef.current;
    interactiveSprite.eventMode = 'static';
    interactiveSprite.cursor = 'pointer';
    const onPointerMove = (event: { global: { x: number; y: number } }) => {
      setSelectedId(pickObject(event.global.x, event.global.y));
    };
    const onPointerTap = (event: { global: { x: number; y: number } }) => {
      const id = pickObject(event.global.x, event.global.y);
      if (id) onSelect?.(id);
    };
    interactiveSprite.on('pointermove', onPointerMove);
    interactiveSprite.on('pointertap', onPointerTap);
    return () => {
      interactiveSprite.off('pointermove', onPointerMove);
      interactiveSprite.off('pointertap', onPointerTap);
    };
  }, [app, onSelect, selectedId]);

  const renderFrame = useCallback(() => {
    if (!sceneRef.current) return;
    const freezeVisualClock = import.meta.env.DEV && new URLSearchParams(window.location.search).has('qaFreeze');
    drawOfficeFrame(
      sceneRef.current,
      freezeVisualClock ? 1_000 : performance.now(),
      agentState,
      solverState,
      boardData,
      chatMessage,
      chatUntilRef.current,
      motionRef.current,
    );
  }, [agentState, solverState, boardData, chatMessage]);

  useEffect(() => {
    renderFrame();
  }, [renderFrame]);

  useTick((ticker) => {
    frameCounterRef.current.frames += 1;
    const elapsed = performance.now() - frameCounterRef.current.start;
    if (elapsed >= 1000) {
      frameCounterRef.current.fps = Math.round(frameCounterRef.current.frames * 1000 / elapsed);
      frameCounterRef.current.start = performance.now();
      frameCounterRef.current.frames = 0;
    }
    const motion = motionRef.current;
    const delta = Math.min(ticker.deltaMS / 1000, 0.05);
    const target = pathRef.current[0];
    if (target) {
      const dx = target.x - motion.x;
      const dy = target.y - motion.y;
      const distance = Math.hypot(dx, dy);
      const step = delta * 2.5;
      motion.walking = true;
      motion.seated = false;
      motion.waiting = false;
      motion.typingPhase = 0;
      motion.facing = target.facing;
      if (distance <= step) {
        motion.x = target.x;
        motion.y = target.y;
        motion.z = target.z;
        pathRef.current.shift();
        if (!pathRef.current.length) motion.walking = false;
      } else {
        motion.x += (dx / distance) * step;
        motion.y += (dy / distance) * step;
        motion.z = target.z;
      }
    } else if (agentState === 'reporting' && performance.now() - stateStartedRef.current > 4200 && !motion.walking) {
      // Report briefly at the Head station, then follow the fixed return route.
      stateStartedRef.current = Number.POSITIVE_INFINITY;
      pathRef.current = [
        { x: 6.0, y: 5.0, z: 3.5, facing: 'right' },
        { x: 4.0, y: 5.2, z: 3.5, facing: 'right' },
        { x: 3.17, y: 4.7, z: 4.2, facing: 'back' },
      ];
    } else {
      motion.walking = false;
      motion.seated = agentState === 'idle' || agentState === 'working' || agentState === 'waiting';
      motion.waiting = agentState === 'waiting';
      motion.typingPhase = agentState === 'working' ? performance.now() / 95 : 0;
      if (agentState === 'reading_board') motion.facing = 'back';
    }
    renderFrame();
  });

  const texture = sceneRef.current?.texture ?? Texture.EMPTY;
  return (
    <pixiSprite
      ref={spriteRef}
      texture={texture}
      x={0}
      y={0}
      width={FRAME_WIDTH}
      height={FRAME_HEIGHT}
      eventMode="static"
      cursor={selectedId ? 'pointer' : 'default'}
      roundPixels
    />
  );
};

const SceneLifecycleController: React.FC = () => {
  const { app } = useApplication();
  useEffect(() => {
    const onVisibilityChange = () => {
      if (!app) return;
      if (document.hidden) app.ticker.stop();
      else app.ticker.start();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [app]);
  return null;
};

export const OfficeScene: React.FC<OfficeSceneProps> = ({ onSelect }) => {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{ x: number; y: number } | null>(null);

  const onWheel = (event: React.WheelEvent) => {
    event.preventDefault();
    setZoom((current) => Math.max(0.75, Math.min(1.75, current + (event.deltaY < 0 ? 0.125 : -0.125))));
  };

  return (
    <div
      className="office-scene-viewport"
      onWheel={onWheel}
      onPointerDown={(event) => {
        if (event.button === 0 || event.button === 1) dragRef.current = { x: event.clientX, y: event.clientY };
      }}
      onPointerMove={(event) => {
        if (!dragRef.current) return;
        const dx = event.clientX - dragRef.current.x;
        const dy = event.clientY - dragRef.current.y;
        dragRef.current = { x: event.clientX, y: event.clientY };
        setPan((current) => ({ x: current.x + dx, y: current.y + dy }));
      }}
      onPointerUp={() => { dragRef.current = null; }}
      onPointerLeave={() => { dragRef.current = null; }}
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        overflow: 'hidden',
        background: '#050409',
        display: 'grid',
        placeItems: 'center',
        touchAction: 'none',
      }}
    >
      <div
        className="office-canvas-wrapper"
        style={{
          aspectRatio: '16 / 9',
          width: 'min(960px, 100%, calc((100vh - 24px) * 16 / 9))',
          maxHeight: '100%',
          maxWidth: '100%',
          height: 'auto',
          imageRendering: 'pixelated',
          position: 'relative',
          boxShadow: 'rgba(0, 0, 0, 0.85) 0px 20px 60px',
          borderRadius: '4px',
          overflow: 'hidden',
        }}
      >
        <Application
          className="office-pixel-canvas"
          width={FRAME_WIDTH}
          height={FRAME_HEIGHT}
          backgroundColor={0x050409}
          roundPixels
          antialias={false}
          autoDensity={false}
          onInit={(app) => {
            app.stage.eventMode = 'static';
            app.stage.hitArea = app.screen;
          }}
        >
          <SceneLifecycleController />
          <pixiContainer
            x={FRAME_WIDTH / 2 + pan.x}
            y={FRAME_HEIGHT / 2 + pan.y}
            pivot={{ x: FRAME_WIDTH / 2, y: FRAME_HEIGHT / 2 }}
            scale={zoom}
          >
            <OfficeRenderer onSelect={onSelect} />
          </pixiContainer>
          <pixiGraphics
            draw={(graphics) => {
              graphics.clear();
              graphics.rect(0, 0, FRAME_WIDTH, 3).fill({ color: 0x050409, alpha: 0.25 });
              graphics.rect(0, FRAME_HEIGHT - 3, FRAME_WIDTH, 3).fill({ color: 0x050409, alpha: 0.25 });
              graphics.rect(0, 0, 3, FRAME_HEIGHT).fill({ color: 0x050409, alpha: 0.25 });
              graphics.rect(FRAME_WIDTH - 3, 0, 3, FRAME_HEIGHT).fill({ color: 0x050409, alpha: 0.25 });
            }}
          />
        </Application>
      </div>

      <div style={controlsStyle}>
        <span>Virtual Office • {OFFICE_WIDTH}×{OFFICE_HEIGHT} → 960×540 • Zoom {Math.round(zoom * 100)}%</span>
        <button style={buttonStyle} onClick={() => setZoom((z) => Math.min(1.75, z + 0.125))}>+</button>
        <button style={buttonStyle} onClick={() => setZoom((z) => Math.max(0.75, z - 0.125))}>−</button>
        <button style={buttonStyle} onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>Reset</button>
      </div>
    </div>
  );
};

function pickObject(frameX: number, frameY: number): string | null {
  const localX = frameX / DESIGN_SCALE_X;
  const localY = frameY / DESIGN_SCALE_Y;
  if (localX >= 205 && localX <= 255 && localY >= 18 && localY <= 48) return 'whiteboard_main';
  if (localX >= 150 && localX <= 190 && localY >= 120 && localY <= 172) return 'solver_station';
  if (localX >= 5 && localX <= 72 && localY >= 55 && localY <= 140) return 'ie_desk';
  return null;
}

const controlsStyle: React.CSSProperties = {
  position: 'absolute',
  right: 18,
  bottom: 18,
  zIndex: 45,
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '7px 10px',
  borderRadius: 6,
  background: 'rgba(15, 23, 42, 0.9)',
  border: '1px solid rgba(56, 189, 248, 0.25)',
  color: '#cbd5e1',
  font: '11px monospace',
};

const buttonStyle: React.CSSProperties = {
  padding: '3px 8px',
  borderRadius: 4,
  border: '1px solid #475569',
  color: '#e2e8f0',
  background: '#1e293b',
  cursor: 'pointer',
};
