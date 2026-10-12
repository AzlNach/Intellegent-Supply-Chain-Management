import { Texture } from 'pixi.js';
import type { AgentState, BoardData, SolverState } from './types';

export const OFFICE_WIDTH = 352;
export const OFFICE_HEIGHT = 196;
const PIXEL_RENDER_SCALE = 2;

type Point = [number, number];
type Light = [number, number];
type SceneCanvas = {
  canvas: HTMLCanvasElement;
  context: CanvasRenderingContext2D;
  baseCanvas: HTMLCanvasElement;
  texture: Texture;
  lights: Light[];
  particles: Array<{ i: number; u: number; n: number; k: number }>;
  boards: Point[];
};

export interface AgentMotion {
  x: number;
  y: number;
  z: number;
  facing: 'front' | 'back' | 'left' | 'right';
  walking: boolean;
  typingPhase: number;
  seated: boolean;
  waiting: boolean;
}

const N = 11;
const A = 14;
const B = 7;
const OX = 176;
const OY = 38;
const WALL_HEIGHT = 36;
const WINDOWS = [9.3, 5.3, 1.3];
const WOOD = ['#dc8f3d', '#a8581b', '#c3711f'];
const BOOK_COLORS = ['#8c2f2a', '#2f5a7a', '#c9a23c', '#3e7a4a', '#6a3a7a', '#d9d2b8', '#a85a2a'];
const NEON: Record<SolverState, { text: string; rgb: string }> = {
  idle: { text: 'IDLE', rgb: '96,210,255' },
  working: { text: 'WORK', rgb: '255,178,58' },
  done: { text: 'DONE', rgb: '109,255,154' },
};
const PIXEL_GLYPHS: Record<string, string> = {
  A: '010101101111101', D: '110101101101110', E: '111100110100111', I: '111010010010111',
  K: '101101110101101', N: '101111111111101', O: '111101101101111', R: '110101110101101',
  W: '101101101111111', ' ': '000000000000000',
};

const project = (x: number, y: number, z = 0): Point => [OX + (x - y) * A, OY + (x + y) * B - z];

function polygon(ctx: CanvasRenderingContext2D, color: string | CanvasGradient, points: Point[]) {
  ctx.fillStyle = color;
  ctx.beginPath();
  points.forEach(([x, y], i) => (i ? ctx.lineTo(Math.round(x), Math.round(y)) : ctx.moveTo(Math.round(x), Math.round(y))));
  ctx.closePath();
  ctx.fill();
}

function rect(ctx: CanvasRenderingContext2D, color: string, x: number, y: number, width: number, height: number) {
  ctx.fillStyle = color;
  ctx.fillRect(Math.round(x), Math.round(y), width, height);
}

function disc(ctx: CanvasRenderingContext2D, cx: number, cy: number, radius: number, color: string) {
  ctx.fillStyle = color;
  for (let y = -radius; y <= radius; y++) {
    const width = Math.floor(Math.sqrt(radius * radius - y * y));
    ctx.fillRect(cx - width, cy + y, 2 * width + 1, 1);
  }
}

function pixelLine(ctx: CanvasRenderingContext2D, x0: number, y0: number, x1: number, y1: number, color: string, thickness = 2) {
  let x = Math.round(x0);
  let y = Math.round(y0);
  const endX = Math.round(x1);
  const endY = Math.round(y1);
  const dx = Math.abs(endX - x);
  const sx = x < endX ? 1 : -1;
  const dy = -Math.abs(endY - y);
  const sy = y < endY ? 1 : -1;
  let error = dx + dy;
  while (true) {
    ctx.fillStyle = color;
    ctx.fillRect(x, y, thickness, thickness);
    if (x === endX && y === endY) break;
    const twiceError = 2 * error;
    if (twiceError >= dy) {
      error += dy;
      x += sx;
    }
    if (twiceError <= dx) {
      error += dx;
      y += sy;
    }
  }
}

function box(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  z: number,
  width: number,
  depth: number,
  height: number,
  top: string,
  left: string,
  right: string,
) {
  polygon(ctx, left, [project(x, y + depth, z), project(x + width, y + depth, z), project(x + width, y + depth, z + height), project(x, y + depth, z + height)]);
  polygon(ctx, right, [project(x + width, y, z), project(x + width, y + depth, z), project(x + width, y + depth, z + height), project(x + width, y, z + height)]);
  polygon(ctx, top, [project(x, y, z + height), project(x + width, y, z + height), project(x + width, y + depth, z + height), project(x, y + depth, z + height)]);
}

function createScene(): SceneCanvas {
  const canvas = document.createElement('canvas');
  canvas.width = OFFICE_WIDTH * PIXEL_RENDER_SCALE;
  canvas.height = OFFICE_HEIGHT * PIXEL_RENDER_SCALE;
  const context = canvas.getContext('2d', { alpha: false })!;
  context.scale(PIXEL_RENDER_SCALE, PIXEL_RENDER_SCALE);
  context.imageSmoothingEnabled = false;
  const texture = Texture.from(canvas);
  texture.source.scaleMode = 'nearest';

  let seed = 7;
  const random = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const lights: Light[] = [];
  const boards: Point[] = [];

  // Checkerboard floor, perimeter fascia and subtle tile seams.
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      const dark = ((i >> 1) + (j >> 1)) % 2;
      const variation = Math.floor(random() * 16);
      polygon(context, `rgb(${dark ? 204 - variation : 238 - variation},${dark ? 146 - variation : 190 - variation},${dark ? 90 - variation : 122 - variation})`, [project(i, j), project(i + 1, j), project(i + 1, j + 1), project(i, j + 1)]);
    }
  }
  polygon(context, '#5a2d12', [project(0, N), project(N, N), project(N, N, -5), project(0, N, -5)]);
  polygon(context, '#3a1b0a', [project(N, 0), project(N, N), project(N, N, -5), project(N, 0, -5)]);
  for (let i = 0; i <= N; i++) {
    polygon(context, 'rgba(90,45,15,.16)', [project(i, 0), project(i + 0.04, 0), project(i + 0.04, N), project(i, N)]);
    polygon(context, 'rgba(90,45,15,.16)', [project(0, i), project(0, i + 0.04), project(N, i + 0.04), project(N, i)]);
  }

  // Warm central carpet/rug.
  polygon(context, '#6e2b2a', [project(3, 5.2), project(8.6, 5.2), project(8.6, 6.8), project(3, 6.8)]);
  polygon(context, '#8f3b32', [project(3.15, 5.35), project(8.45, 5.35), project(8.45, 6.65), project(3.15, 6.65)]);
  polygon(context, '#c9923e', [project(3.35, 5.55), project(8.25, 5.55), project(8.25, 6.45), project(3.35, 6.45)]);
  polygon(context, '#7a3030', [project(3.5, 5.7), project(8.1, 5.7), project(8.1, 6.3), project(3.5, 6.3)]);

  // Wall shadows and warm timber base trim.
  polygon(context, 'rgba(10,5,25,.3)', [project(0, 0), project(0, N), project(0.7, N), project(0.7, 0)]);
  polygon(context, 'rgba(10,5,25,.16)', [project(0.7, 0), project(0.7, N), project(1.5, N), project(1.5, 0)]);
  polygon(context, 'rgba(10,5,25,.3)', [project(0, 0), project(N, 0), project(N, 0.7), project(0, 0.7)]);
  polygon(context, 'rgba(10,5,25,.16)', [project(0, 0.7), project(N, 0.7), project(N, 1.5), project(0, 1.5)]);

  // Isometric night-blue walls, baseboards, panel seams, and top cap.
  polygon(context, '#2b2a57', [project(0, 0), project(0, N), project(0, N, WALL_HEIGHT), project(0, 0, WALL_HEIGHT)]);
  polygon(context, '#222146', [project(0, 0), project(N, 0), project(N, 0, WALL_HEIGHT), project(0, 0, WALL_HEIGHT)]);
  polygon(context, '#6b3a1a', [project(0, 0), project(0, N), project(0, N, 3), project(0, 0, 3)]);
  polygon(context, '#5a2f14', [project(0, 0), project(N, 0), project(N, 0, 3), project(0, 0, 3)]);
  polygon(context, '#1a1936', [project(0, 0, WALL_HEIGHT), project(0, N, WALL_HEIGHT), project(0, N, WALL_HEIGHT - 2), project(0, 0, WALL_HEIGHT - 2)]);
  polygon(context, 'rgba(0,0,0,.22)', [project(0, 0, 3), project(0, N, 3), project(0, N, 13), project(0, 0, 13)]);
  polygon(context, 'rgba(0,0,0,.26)', [project(0, 0, 3), project(N, 0, 3), project(N, 0, 13), project(0, 0, 13)]);
  for (let y = 1; y < N; y++) polygon(context, 'rgba(0,0,0,.2)', [project(0, y, 3), project(0, y + 0.05, 3), project(0, y + 0.05, WALL_HEIGHT - 2), project(0, y, WALL_HEIGHT - 2)]);
  for (let x = 1; x < N; x++) polygon(context, 'rgba(0,0,0,.22)', [project(x, 0, 3), project(x + 0.05, 0, 3), project(x + 0.05, 0, WALL_HEIGHT - 2), project(x, 0, WALL_HEIGHT - 2)]);
  polygon(context, '#7a4620', [project(0, 0, 13), project(0, N, 13), project(0, N, 14.5), project(0, 0, 14.5)]);
  polygon(context, '#6a3a18', [project(0, 0, 13), project(N, 0, 13), project(N, 0, 14.5), project(0, 0, 14.5)]);
  polygon(context, '#4a3f78', [project(0, 0, WALL_HEIGHT - 1), project(0, N, WALL_HEIGHT - 1), project(0, N, WALL_HEIGHT), project(0, 0, WALL_HEIGHT)]);
  polygon(context, '#3d3566', [project(0, 0, WALL_HEIGHT - 1), project(N, 0, WALL_HEIGHT - 1), project(N, 0, WALL_HEIGHT), project(0, 0, WALL_HEIGHT)]);

  // Golden windows on the left wall, with wood framing and sill boxes.
  WINDOWS.forEach((windowY) => {
    polygon(context, '#8a4a1c', [project(0, windowY - 0.1, 9), project(0, windowY + 1.6, 9), project(0, windowY + 1.6, 31), project(0, windowY - 0.1, 31)]);
    polygon(context, '#ffe3a3', [project(0, windowY, 10), project(0, windowY + 1.5, 10), project(0, windowY + 1.5, 30), project(0, windowY, 30)]);
    for (let z = 21; z < 30; z += 2) polygon(context, '#e8b565', [project(0, windowY, z), project(0, windowY + 1.5, z), project(0, windowY + 1.5, z + 1), project(0, windowY, z + 1)]);
  });
  WINDOWS.forEach((windowY) => {
    polygon(context, '#8a4a1c', [project(0, windowY + 0.72, 10), project(0, windowY + 0.78, 10), project(0, windowY + 0.78, 30), project(0, windowY + 0.72, 30)]);
    polygon(context, '#8a4a1c', [project(0, windowY, 19.5), project(0, windowY + 1.5, 19.5), project(0, windowY + 1.5, 20.5), project(0, windowY, 20.5)]);
    box(context, 0, windowY - 0.12, 8.5, 0.4, 1.74, 1.5, '#c47a30', '#8a4a1c', '#a85a22');
    polygon(context, '#4a2a14', [project(0, windowY - 0.25, 32.5), project(0, windowY + 1.75, 32.5), project(0, windowY + 1.75, 33.5), project(0, windowY - 0.25, 33.5)]);
    [[-0.15, 0.25], [1.25, 1.65]].forEach(([a, b]) => {
      polygon(context, '#8a3040', [project(0, windowY + a, 32.5), project(0, windowY + b, 32.5), project(0, windowY + b - 0.05, 10), project(0, windowY + a, 10)]);
      polygon(context, 'rgba(0,0,0,.25)', [project(0, windowY + a + 0.1, 32), project(0, windowY + a + 0.14, 32), project(0, windowY + a + 0.14, 10), project(0, windowY + a + 0.1, 10)]);
    });
  });

  // Bookshelves on both walls. Wood frames, shelf boards, and color-spined books.
  const shelf = (leftWall: boolean, position: number, length: number) => {
    const at = (u: number, z: number): Point => (leftWall ? project(1.2, u, z) : project(u, 1.2, z));
    const top = '#c06a22';
    const left = '#a35a1e';
    const right = '#7d3f12';
    if (leftWall) box(context, 0, position, 0, 1.2, length, 34, top, right, left);
    else box(context, position, 0, 0, length, 1.2, 34, top, left, right);
    polygon(context, '#3e1d0a', [at(position + 0.1, 2), at(position + length - 0.1, 2), at(position + length - 0.1, 33), at(position + 0.1, 33)]);
    for (let row = 0; row < 4; row++) {
      const z = 3 + row * 8;
      for (let u = position + 0.12; u < position + length - 0.2; u += 0.11) {
        const height = 4 + Math.floor(random() * 4);
        polygon(context, BOOK_COLORS[Math.floor(random() * BOOK_COLORS.length)], [at(u, z), at(u + 0.1, z), at(u + 0.1, z + height), at(u, z + height)]);
      }
      polygon(context, '#a35a1e', [at(position, z - 1), at(position + length, z - 1), at(position + length, z), at(position, z)]);
    }
  };
  [[true, 7.2, 1.9], [true, 3.2, 1.9], [false, 8.1, 1.0]].forEach(([wall, position, length]) => shelf(Boolean(wall), Number(position), Number(length)));

  // Windowside office props and potted plants.
  box(context, 0.3, 7.4, 34, 0.6, 0.7, 3, '#d8c8a0', '#b4a47c', '#9c8c68');
  box(context, 0.35, 8.3, 34, 0.5, 0.6, 2, '#6a8ab0', '#4a6a90', '#3a5a80');
  box(context, 0.3, 3.4, 34, 0.6, 0.5, 2, '#a85a2a', '#86441c', '#6e3818');
  box(context, 0.3, 4.2, 34, 0.6, 0.8, 4, '#d8c8a0', '#b4a47c', '#9c8c68');
  box(context, 8.2, 0.3, 34, 0.5, 0.6, 3, '#d8c8a0', '#b4a47c', '#9c8c68');
  box(context, 8.7, 0.3, 34, 0.3, 0.5, 2, '#7a9a5a', '#5a7a3a', '#486a2a');

  const plant = (x: number, y: number, big: boolean) => {
    const [screenX, screenY] = project(x, y, 5).map(Math.round);
    const radius = big ? 9 : 7;
    box(context, x - 0.35, y - 0.35, 0, 0.7, 0.7, 4, '#e08334', '#b8601f', '#c8691f');
    box(context, x - 0.42, y - 0.42, 4, 0.84, 0.84, 1.2, '#f09844', '#c8702a', '#a85a1e');
    polygon(context, '#3a2210', [project(x - 0.34, y - 0.34, 5.2), project(x + 0.34, y - 0.34, 5.2), project(x + 0.34, y + 0.34, 5.2), project(x - 0.34, y + 0.34, 5.2)]);
    rect(context, '#6b3a1a', screenX - 1, screenY - 14, 2, 14);
    disc(context, screenX, screenY - 14 - radius, radius, '#2f5226');
    disc(context, screenX - 2, screenY - 16 - radius, radius - 2, '#4a7a30');
    disc(context, screenX - 3, screenY - 18 - radius, radius - 5, '#7aa845');
    for (let k = 0; k < 6; k++) rect(context, '#9cc25a', screenX - radius + Math.floor(random() * radius * 2), screenY - 12 - radius * 2 + Math.floor(random() * radius * 2), 1, 1);
  };
  plant(0.9, 0.9, false);
  plant(0.9, 10, true);
  plant(10.5, 0.7, true);

  // Whiteboard uses the reference HTML's exact geometry only for placement/size.
  // Its existing live stock-board content is painted during drawFrame().
  const wb = (x: number, z: number): Point => project(2.3 + (x - 3.8) * 0.842, 0, z);
  polygon(context, '#8a5a2b', [wb(3.8, 11), wb(7.6, 11), wb(7.6, 33), wb(3.8, 33)]);
  polygon(context, '#d6cfba', [wb(3.9, 12), wb(7.5, 12), wb(7.5, 32), wb(3.9, 32)]);
  const clockCenter = project(6.3, 0, 27);
  const clockRing = (radius: number): Point[] => Array.from({ length: 14 }, (_, index) => {
    const angle = (index / 14) * Math.PI * 2;
    return [clockCenter[0] + Math.cos(angle) * radius, clockCenter[1] + Math.cos(angle) * radius * 0.5 - Math.sin(angle) * radius];
  });
  polygon(context, '#6b4a28', clockRing(6));
  polygon(context, '#efe6d0', clockRing(4.8));
  for (let tick = 0; tick < 12; tick++) {
    const angle = (tick / 12) * Math.PI * 2;
    rect(context, '#3a2a1a', clockCenter[0] + Math.sin(angle) * 4, clockCenter[1] + Math.sin(angle) * 2 - Math.cos(angle) * 4, 1, 1);
  }
  polygon(context, '#7a5a30', [wb(4.6, 10), wb(6.8, 10), wb(6.8, 11.5), wb(4.6, 11.5)]);
  polygon(context, '#c8453a', [wb(5, 11.5), wb(5.4, 11.5), wb(5.4, 12.5), wb(5, 12.5)]);
  polygon(context, '#3a6ab0', [wb(5.6, 11.5), wb(6, 11.5), wb(6, 12.5), wb(5.6, 12.5)]);
  // Utility objects from the supplied composition.
  box(context, 9.5, 5.6, 0, 0.8, 0.8, 9, '#dfe4ec', '#b9bfca', '#9aa1ad');
  box(context, 9.6, 5.7, 9, 0.6, 0.6, 7, '#a5d6f2', '#7eb8dc', '#5f9cc4');
  box(context, 9.65, 5.75, 16, 0.5, 0.5, 0.8, '#dfe4ec', '#b9bfca', '#9aa1ad');
  box(context, 1.25, 6.2, 0, 0.5, 0.5, 4, '#6a6a78', '#50505c', '#3e3e48');

  // People, desks, CRT monitors, and warm lamps from the designed composition.
  const personColors: Array<[[string, string, string], [string, string, string], [string, string, string]]> = [
    [['#8a3fa0', '#3a2418', '#c68642'], ['#e07a2a', '#5a2a14', '#f0b27a'], ['#4f9a3a', '#2a1a10', '#f0b27a']],
    [['#3fa05a', '#c8651f', '#f0b27a'], ['#7a3a9a', '#1a1a1a', '#8d5524'], ['#7a3a9a', '#7a2a14', '#f5cba7']],
    [['#3f78c8', '#b8602a', '#f0b27a'], ['#e07a2a', '#7a3a1c', '#f0b27a'], ['#e8601c', '#3a2a1c', '#c68642']],
    [['#9a3a2a', '#4a2a1a', '#c68642'], ['#e8901c', '#1a1a1a', '#8d5524'], ['#3f78a8', '#5a3a1a', '#f0b27a']],
  ];

  const person = (
    x: number,
    y: number,
    colors: [string, string, string],
    facing: AgentMotion['facing'],
    animation: 'idle' | 'working' | 'walking' | 'reading' | 'waiting' | 'reporting' = 'idle',
    phase = 0,
  ) => {
    const walkBob = animation === 'walking' || animation === 'reporting' ? (Math.floor(phase) % 2 ? -1 : 0) : 0;
    const typeBob = animation === 'working' ? (Math.floor(phase) % 2 ? -1 : 0) : 0;
    const [screenX, screenY] = project(x, y, 4 + walkBob + typeBob).map(Math.round);
    const [shirt, hair, skin] = colors;
    const facingFront = facing === 'front';
    const seated = animation === 'idle' || animation === 'working' || animation === 'waiting';
    rect(context, '#3a3a47', screenX - 4, screenY - (facingFront ? 11 : 6), 8, facingFront ? 10 : 6);
    rect(context, '#2d2d38', screenX - 4, screenY - 1, 8, 3);
    rect(context, '#1e1e26', screenX - 1, screenY + 2, 2, 3);
    rect(context, '#1e1e26', screenX - 4, screenY + 5, 8, 1);
    if (facingFront) {
      rect(context, shirt, screenX - 3, screenY - 10, 6, 9);
      const handLift = animation === 'working' ? (Math.floor(phase * 2) % 2 ? 2 : 0) : animation === 'idle' ? (Math.floor(phase * 2) % 2 ? 1 : 0) : 0;
      rect(context, shirt, screenX - 4, screenY - 8 + handLift, 1, 5);
      rect(context, shirt, screenX + 3, screenY - 8 - handLift, 1, 5);
      rect(context, skin, screenX - 4, screenY - 3 + handLift, 1, 2);
      rect(context, skin, screenX + 3, screenY - 3 - handLift, 1, 2);
      if (seated) {
        rect(context, '#293144', screenX - 4, screenY - 1, 3, 4);
        rect(context, '#293144', screenX + 1, screenY - 1, 3, 4);
      }
      rect(context, skin, screenX - 2, screenY - 15, 4, 5);
      rect(context, hair, screenX - 2, screenY - 16, 4, 2);
      rect(context, hair, screenX - 3, screenY - 15, 1, 3);
      rect(context, hair, screenX + 2, screenY - 15, 1, 3);
      rect(context, '#222222', screenX - 1, screenY - 13, 1, 1);
      rect(context, '#222222', screenX + 1, screenY - 13, 1, 1);
    } else {
      rect(context, shirt, screenX - 3, screenY - 10, 6, 9);
      if (facing === 'left') rect(context, skin, screenX - 4, screenY - 13, 2, 2);
      if (facing === 'right') rect(context, skin, screenX + 2, screenY - 13, 2, 2);
      rect(context, skin, screenX - 2, screenY - 15, 4, 5);
      rect(context, hair, screenX - 2, screenY - 16, 4, 4);
      rect(context, '#3a3a47', screenX - 4, screenY - 6, 8, 6);
    }
  };

  const monitor = (x: number, y: number) => {
    box(context, x + 0.2, y + 0.2, 7, 0.4, 0.3, 1, '#c9bf9d', '#b5aa88', '#a89e7e');
    box(context, x, y, 8, 0.75, 0.65, 7, '#e4dcc0', '#cfc6a4', '#b9b090');
    const screen = [project(x + 0.08, y + 0.65, 9.2), project(x + 0.67, y + 0.65, 9.2), project(x + 0.67, y + 0.65, 14.2), project(x + 0.08, y + 0.65, 14.2)];
    polygon(context, '#0c2416', screen);
    boards.push(screen[3].map(Math.round) as Point);
    box(context, x + 0.05, y + 0.95, 7, 0.6, 0.28, 0.7, '#d8d0b8', '#b9b19a', '#c4bca4');
  };

  const lamp = (x: number, y: number) => {
    const [screenX, screenY] = project(x, y, 7).map(Math.round);
    rect(context, '#4a2a12', screenX - 2, screenY - 1, 4, 1);
    rect(context, '#3a2a1a', screenX, screenY - 6, 1, 5);
    rect(context, '#ffd25e', screenX - 3, screenY - 10, 7, 4);
    rect(context, '#fff0b0', screenX - 2, screenY - 10, 4, 1);
    lights.push([screenX, screenY - 8]);
  };

  const drawWoodenDesk = (x: number, y: number) => {
    polygon(context, 'rgba(40,15,5,.32)', [project(x + 0.4, y), project(x + 4.2, y), project(x + 4.2, y + 1.4), project(x + 0.4, y + 1.4)]);
    box(context, x, y, 0, 2.8, 1.4, 7, WOOD[0], WOOD[1], WOOD[2]);
  };

  const workstation = (x: number, y: number, colors?: [string, string, string]) => {
    drawWoodenDesk(x, y);
    box(context, x, y, 5.5, 2.6, 1.4, 1.5, WOOD[0], WOOD[1], WOOD[2]);
    box(context, x + 1.6, y + 0.1, 0, 0.85, 1.2, 5.5, '#c3711f', '#a8581b', '#7d3f12');
    [1.6, 3.2].forEach((z) => polygon(context, '#3a2210', [project(x + 1.85, y + 1.3, z), project(x + 2.2, y + 1.3, z), project(x + 2.2, y + 1.3, z + 0.5), project(x + 1.85, y + 1.3, z + 0.5)]));
    monitor(x + 0.9, y + 0.1);
    lamp(x + 2.1, y + 0.5);
    box(context, x + 0.15, y + 0.35, 7, 0.5, 0.6, 0.6, '#efe9d8', '#cfc8b0', '#aaa38f');
    box(context, x + 0.2, y + 0.4, 7.6, 0.4, 0.5, 0.3, '#3a6a9a', '#254b70', '#1d3c5a');
    box(context, x + 2.0, y + 1.0, 7, 0.2, 0.2, 1.3, '#e8e8e8', '#cfcfcf', '#b0b0b0');
    box(context, x + 1.75, y + 1.0, 7, 0.14, 0.2, 0.4, '#cfc8b0', '#aaa38f', '#8c8778');
    polygon(context, '#7cff7c', [project(x + 1.55, y + 0.76, 9.3), project(x + 1.6, y + 0.76, 9.3), project(x + 1.6, y + 0.76, 9.6), project(x + 1.55, y + 0.76, 9.6)]);
    const chairX = x + 1.27;
    const chairY = y + 2.1;
    box(context, chairX - 0.35, chairY - 0.05, 0, 0.7, 0.1, 0.6, '#2a2a33', '#20202a', '#17171f');
    box(context, chairX - 0.05, chairY - 0.35, 0, 0.1, 0.7, 0.6, '#2a2a33', '#20202a', '#17171f');
    box(context, chairX - 0.06, chairY - 0.06, 0.6, 0.12, 0.12, 2.6, '#2a2a33', '#20202a', '#17171f');
    box(context, chairX - 0.32, chairY - 0.32, 3.2, 0.64, 0.64, 1, '#454556', '#343442', '#282834');
    box(context, chairX - 0.32, chairY + 0.2, 4.2, 0.64, 0.12, 5.5, '#454556', '#343442', '#282834');
    if (colors) person(chairX, chairY, colors, 'front', 'idle');
  };

  // Four desk groups from the supplied HTML composition.
  workstation(1.9, 2.6);
  workstation(6.3, 2.6, personColors[1][0]);
  workstation(1.9, 7.0, personColors[2][0]);
  workstation(6.3, 7.0, personColors[3][0]);

  const baseCanvas = document.createElement('canvas');
  baseCanvas.width = canvas.width;
  baseCanvas.height = canvas.height;
  baseCanvas.getContext('2d')!.drawImage(canvas, 0, 0);
  const dust = Array.from({ length: 90 }, () => ({ i: Math.floor(random() * 3), u: random(), n: random() * 6.28, k: random() }));
  return { canvas, context, baseCanvas, texture, lights, particles: dust, boards };
}

const STATUS_LABELS: Record<AgentState, string> = {
  idle: 'Menunggu tugas',
  reading_board: 'Membaca papan',
  working: 'Memproses data',
  waiting: 'Menunggu jawaban Anda',
  reporting: 'Melapor',
};

function roundedBubble(ctx: CanvasRenderingContext2D, x: number, y: number, text: string) {
  ctx.font = '600 6px system-ui, sans-serif';
  const width = Math.max(46, Math.ceil(ctx.measureText(text).width) + 10);
  const height = 11;
  const left = Math.round(x - width / 2);
  const top = Math.round(y - height);
  ctx.fillStyle = 'rgba(15,8,20,.34)';
  ctx.fillRect(left + 1, top + 2, width, height);
  ctx.fillStyle = '#ecebe6';
  ctx.strokeStyle = '#6a6470';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(left, top, width, height, 2);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(x - 3, top + height - 1);
  ctx.lineTo(x + 3, top + height - 1);
  ctx.lineTo(x, top + height + 3);
  ctx.closePath();
  ctx.fillStyle = '#ecebe6';
  ctx.fill();
  ctx.fillStyle = '#241f2b';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, x, top + height / 2 + 0.5, width - 6);
  ctx.textAlign = 'start';
}

function drawMovingAgent(ctx: CanvasRenderingContext2D, motion: AgentMotion, time: number) {
  const walk = motion.walking;
  const bob = walk ? (Math.floor(time / 120) % 2 ? -1 : 0) : motion.typingPhase ? Math.floor(motion.typingPhase * 2) % 2 : 0;
  const [x, y] = project(motion.x, motion.y, motion.z + bob).map(Math.round);
  const shirt = '#4f9a3a';
  const hair = '#2a1a10';
  const skin = '#f0b27a';

  // Dedicated seated pose for idle/working/waiting. Return early so standing limbs
  // cannot be drawn on top of the chair pose.
  ctx.fillStyle = 'rgba(10,5,12,.35)';
  ctx.fillRect(x - 7, y + 4, 14, 2);
  if (motion.seated) {
    // Legs fold at the existing workstation chair; do not paint a second chair.
    rect(ctx, '#293144', x - 4, y - 2, 8, 2);
    rect(ctx, '#293144', x - 4, y, 3, 3);
    rect(ctx, '#293144', x + 1, y, 3, 3);
    rect(ctx, '#1e1e26', x - 5, y + 2, 4, 2);
    rect(ctx, '#1e1e26', x + 1, y + 2, 4, 2);

    // Keyboard is down-right of the character in this isometric composition.
    // Extend both elbows and hands to that surface, below the face and torso.
    if (motion.typingPhase > 0) {
      const tap = Math.floor(time / 100) % 2;
      // Keep forearms level with the shoulders and slightly lower toward the desktop.
      const handY = y - 8 + tap;
      pixelLine(ctx, x - 2, y - 9, x + 9, handY, shirt, 2);
      pixelLine(ctx, x + 2, y - 9, x + 13, y - 8 + (tap ? 0 : 1), shirt, 2);
      rect(ctx, skin, x + 9, handY, 2, 2);
      rect(ctx, skin, x + 13, y - 8 + (tap ? 0 : 1), 2, 2);
    } else {
      // Idle arms also rest forward on the desktop, clear of the torso.
      rect(ctx, shirt, x - 2, y - 9, 3, 3);
      rect(ctx, shirt, x + 1, y - 7, 3, 3);
      rect(ctx, skin, x + 4, y - 4, 3, 2);
      rect(ctx, shirt, x + 2, y - 9, 3, 3);
      rect(ctx, shirt, x + 5, y - 7, 3, 3);
      rect(ctx, skin, x + 8, y - 4, 3, 2);
    }
    rect(ctx, shirt, x - 4, y - 10, 8, 8);
    rect(ctx, skin, x - 2, y - 17, 5, 6);
    rect(ctx, hair, x - 3, y - 19, 7, 4);
    rect(ctx, hair, x - 4, y - 17, 2, 4);
    rect(ctx, '#241f2b', x - 1, y - 14, 1, 1);

    if (motion.waiting) {
      rect(ctx, '#f4c542', x - 2, y - 28, 5, 2);
      rect(ctx, '#f4c542', x - 1, y - 26, 3, 2);
      rect(ctx, '#fff0b0', x, y - 24, 1, 1);
      rect(ctx, '#f4c542', x - 2, y - 23, 5, 2);
    }
    return;
  }

  const front = motion.facing === 'front';
  const back = motion.facing === 'back';
  if (front) {
    rect(ctx, shirt, x - 4, y - 13, 8, 10);
    rect(ctx, skin, x - 2, y - 19, 5, 6);
    rect(ctx, hair, x - 3, y - 20, 7, 3);
    rect(ctx, hair, x - 4, y - 18, 2, 3);
    rect(ctx, '#241f2b', x - 1, y - 16, 1, 1);
    rect(ctx, '#241f2b', x + 2, y - 16, 1, 1);
  } else if (back) {
    rect(ctx, shirt, x - 4, y - 13, 8, 10);
    rect(ctx, hair, x - 3, y - 20, 7, 7);
    rect(ctx, skin, x - 2, y - 14, 4, 2);
  } else {
    rect(ctx, shirt, x - 4, y - 13, 8, 10);
    rect(ctx, skin, x - 3, y - 19, 6, 6);
    rect(ctx, hair, x - 3, y - 20, 7, 3);
    const faceX = motion.facing === 'left' ? x - 4 : x + 2;
    rect(ctx, '#241f2b', faceX, y - 16, 1, 1);
  }

  // Arms: alternating movement gives readable typing/walking states at low resolution.
  const arm = motion.typingPhase > 0 ? Math.floor(time / 90) % 2 : 0;
  rect(ctx, shirt, x - 6, y - 12 + (arm ? 1 : 0), 2, 7);
  rect(ctx, shirt, x + 4, y - 12 + (arm ? 0 : 1), 2, 7);
  rect(ctx, skin, x - 6, y - 5 + (arm ? 1 : 0), 2, 2);
  rect(ctx, skin, x + 4, y - 5 + (arm ? 0 : 1), 2, 2);

  // Pixel-leg stride, feet, and cast shadow.
  if (walk) {
    const stride = Math.floor(time / 120) % 2;
    rect(ctx, '#293144', x - 3 - stride, y - 3, 2, 6);
    rect(ctx, '#293144', x + 1 + stride, y - 3, 2, 6);
    rect(ctx, '#1e1e26', x - 4 - stride, y + 2, 3, 2);
    rect(ctx, '#1e1e26', x + 1 + stride, y + 2, 3, 2);
  } else {
    rect(ctx, '#293144', x - 3, y - 3, 2, 6);
    rect(ctx, '#293144', x + 1, y - 3, 2, 6);
    rect(ctx, '#1e1e26', x - 4, y + 2, 3, 2);
    rect(ctx, '#1e1e26', x + 1, y + 2, 3, 2);
  }

  if (motion.facing === 'back' && !walk && motion.z > 4.5) {
    ctx.fillStyle = '#ffd27a';
    ctx.font = 'bold 7px monospace';
    ctx.fillText('!', x - 1, y - 22);
  }
  if (motion.waiting) {
    rect(ctx, '#f4c542', x - 2, y - 28, 5, 2);
    rect(ctx, '#f4c542', x - 1, y - 26, 3, 2);
    rect(ctx, '#fff0b0', x, y - 24, 1, 1);
    rect(ctx, '#f4c542', x - 2, y - 23, 5, 2);
  }
}

function drawFrame(
  scene: SceneCanvas,
  time: number,
  agentState: AgentState,
  solverState: SolverState,
  boardData: BoardData,
  chatMessage: string | null,
  chatUntil: number,
  agentMotion: AgentMotion,
) {
  const { context: ctx, lights, particles, boards } = scene;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalCompositeOperation = 'source-over';
  ctx.clearRect(0, 0, scene.canvas.width, scene.canvas.height);
  ctx.drawImage(scene.baseCanvas, 0, 0);
  ctx.setTransform(PIXEL_RENDER_SCALE, 0, 0, PIXEL_RENDER_SCALE, 0, 0);

  // Live stock board occupies the exact parallelogram defined by the HTML wb(x,z) anchors.
  // The furniture/frame coordinates are retained; only the data face is rendered here.
  const boardTopLeft = project(2.3, 0, 33);
  const boardTopRight = project(5.5, 0, 33);
  const boardBottomLeft = project(2.3, 0, 11);
  const boardWidth = 96;
  const boardHeight = 48;
  ctx.save();
  ctx.transform(
    (boardTopRight[0] - boardTopLeft[0]) / boardWidth,
    (boardTopRight[1] - boardTopLeft[1]) / boardWidth,
    (boardBottomLeft[0] - boardTopLeft[0]) / boardHeight,
    (boardBottomLeft[1] - boardTopLeft[1]) / boardHeight,
    boardTopLeft[0],
    boardTopLeft[1],
  );
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = '#d6cfba';
  ctx.fillRect(3, 3, boardWidth - 6, boardHeight - 6);
  ctx.fillStyle = '#173d56';
  ctx.fillRect(4, 4, boardWidth - 8, 8);
  ctx.fillStyle = '#e8f5ff';
  ctx.font = 'bold 5px monospace';
  ctx.textBaseline = 'middle';
  ctx.fillText('SCDS-OR STOCK BOARD', 7, 8);

  const boardRows = [
    ['PRODUCT', boardData.fields.product_id],
    ['ON HAND', boardData.fields.on_hand_qty],
    ['TARGET', boardData.fields.target_qty],
    ['OUTGOING', boardData.fields.expected_outgoing_qty],
    ['REQUIRED BY', boardData.fields.required_by],
  ] as const;
  boardRows.forEach(([label, field], index) => {
    const y = 14 + index * 6.1;
    ctx.fillStyle = index % 2 === 0 ? '#eee9dc' : '#ded8c9';
    ctx.fillRect(5, y, boardWidth - 10, 5.8);
    ctx.fillStyle = '#2b2a35';
    ctx.font = '4px monospace';
    ctx.fillText(label, 7, y + 2.9, 28);
    const value = String(field.value ?? '—');
    ctx.fillText(value.length > 13 ? `${value.slice(0, 12)}…` : value, 37, y + 2.9, 28);
    const chipColor = field.status === 'conflict' ? '#d1433a' : field.status === 'undefined' ? '#858585' : '#2f7a4b';
    ctx.fillStyle = chipColor;
    ctx.fillRect(67, y + 0.7, 11, 4.3);
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 3px monospace';
    ctx.fillText(field.status === 'defined' ? 'OK' : field.status === 'conflict' ? '!' : '—', 70, y + 2.9);
    ctx.fillStyle = '#45424a';
    ctx.font = '3.5px monospace';
    const source = field.source || 'database';
    ctx.fillText(source.length > 12 ? `${source.slice(0, 11)}…` : source, 80, y + 2.9, 13);
  });
  ctx.restore();

  // Isometric neon solver sign shifted left to align its center with the wall clock at x=6.3.
  const neon = NEON[solverState];
  const flicker = Math.sin(time / 53) > 0.985 ? 0.5 : 1;
  const brightness = (0.88 + 0.12 * Math.sin(time / (solverState === 'idle' ? 600 : 170))) * flicker;
  const [signX, signY] = project(5.4, 0, 17.5).map(Math.round);
  const signGlow = ctx.createRadialGradient(signX + 8, signY + 4, 0, signX + 8, signY + 4, 26);
  signGlow.addColorStop(0, `rgba(${neon.rgb},${0.3 * brightness})`);
  signGlow.addColorStop(1, `rgba(${neon.rgb},0)`);
  ctx.globalCompositeOperation = 'lighter';
  ctx.fillStyle = signGlow;
  ctx.fillRect(signX - 20, signY - 22, 56, 52);
  ctx.fillStyle = `rgba(${neon.rgb},${brightness})`;
  const glyphText = ` ${neon.text} `;
  [...glyphText].forEach((character, letterIndex) => {
    const glyph = PIXEL_GLYPHS[character] ?? PIXEL_GLYPHS[' '];
    for (let row = 0; row < 5; row++) {
      for (let column = 0; column < 3; column++) {
        if (glyph[row * 3 + column] === '1') {
          const pixelX = letterIndex * 4 + column;
          ctx.fillRect(signX + pixelX, signY + (pixelX >> 1) + row, 1, 1);
        }
      }
    }
  });
  ctx.globalAlpha = 1;

  // Warm sunbeams from windows, animated subtly.
  const sunlight = 0.82 + 0.18 * Math.sin(time / 900);
  ctx.globalAlpha = 1;
  WINDOWS.forEach((windowY) => {
    const start = project(0, windowY + 0.7, 28);
    const end = project(8, windowY + 3.5, 0);
    const gradient = ctx.createLinearGradient(start[0], start[1], end[0], end[1]);
    gradient.addColorStop(0, `rgba(255,205,120,${0.32 * sunlight})`);
    gradient.addColorStop(1, 'rgba(255,205,120,0)');
    polygon(ctx, gradient, [project(0, windowY, 28), project(0, windowY + 1.5, 28), project(8, windowY + 4, 0), project(8, windowY + 2.5, 0)]);
    polygon(ctx, gradient, [project(0.5, windowY + 0.6), project(0.5, windowY + 1.35), project(8, windowY + 3.85), project(8, windowY + 3.1)]);
    polygon(ctx, gradient, [project(0.5, windowY + 1.45), project(0.5, windowY + 2.1), project(8, windowY + 4.6), project(8, windowY + 3.95)]);

    const glow = project(0, windowY + 0.75, 20);
    const radial = ctx.createRadialGradient(glow[0], glow[1], 0, glow[0], glow[1], 24);
    radial.addColorStop(0, `rgba(255,200,110,${0.28 * sunlight})`);
    radial.addColorStop(1, 'rgba(255,200,110,0)');
    ctx.fillStyle = radial;
    ctx.fillRect(glow[0] - 24, glow[1] - 24, 48, 48);
  });

  // Desk lamp pools of amber light.
  lights.forEach(([x, y], index) => {
    const pulse = 0.85 + 0.15 * Math.sin(time / 430 + index * 2);
    const glow = ctx.createRadialGradient(x, y, 0, x, y, 28);
    glow.addColorStop(0, `rgba(255,185,70,${0.14 * pulse})`);
    glow.addColorStop(1, 'rgba(255,185,70,0)');
    ctx.fillStyle = glow;
    ctx.fillRect(x - 28, y - 28, 56, 56);
  });

  // Green CRT glow and phosphor scan line shimmer.
  boards.forEach(([x, y]) => {
    const glow = ctx.createRadialGradient(x + 4, y + 4, 0, x + 4, y + 4, 13);
    glow.addColorStop(0, 'rgba(90,255,150,.1)');
    glow.addColorStop(1, 'rgba(90,255,150,0)');
    ctx.fillStyle = glow;
    ctx.fillRect(x - 10, y - 10, 28, 28);
  });
  ctx.fillStyle = '#6dff9a';
  boards.forEach(([x, y], index) => {
    for (let line = 0; line < 3; line++) {
      const length = 3 + (((time / 280 + index * 3 + line * 5) | 0) % 5);
      for (let step = 0; step < length; step++) ctx.fillRect(x + step, y + (step >> 1) + line * 2 + 1, 1, 1);
    }
  });

  // Dust particles drift through sunlight.
  particles.forEach((particle) => {
    const start = project(0, WINDOWS[particle.i] + 0.7, 20);
    const end = project(7, WINDOWS[particle.i] + 3.5, 2);
    const u = (particle.u + (time / 60000) * (0.5 + particle.k)) % 1;
    const x = start[0] + (end[0] - start[0]) * u + Math.sin(time / 1500 + particle.n) * 3;
    const y = start[1] + (end[1] - start[1]) * u + Math.cos(time / 1900 + particle.n) * 3;
    ctx.fillStyle = `rgba(255,225,160,${0.25 + 0.5 * Math.abs(Math.sin(time / 700 + particle.n))})`;
    ctx.fillRect(Math.round(x), Math.round(y), 1, 1);
  });

  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'source-over';

  // State-driven IE Agent sprite, layered over the corresponding workstation/path.
  drawMovingAgent(ctx, agentMotion, time);

  // In-scene pixel bubble follows the IE Agent. Chat takes precedence temporarily.
  const label = chatMessage && time < chatUntil ? chatMessage : STATUS_LABELS[agentState];
  const bubble = project(agentMotion.x, agentMotion.y, agentMotion.z + 25);
  roundedBubble(ctx, bubble[0], bubble[1], label.length > 34 ? `${label.slice(0, 32)}…` : label);

  // Vignette from supplied composition.
  const vignette = ctx.createRadialGradient(OFFICE_WIDTH / 2, OFFICE_HEIGHT / 2 + 10, 50, OFFICE_WIDTH / 2, OFFICE_HEIGHT / 2 + 10, OFFICE_WIDTH * 0.6);
  vignette.addColorStop(0, 'rgba(8,4,20,0)');
  vignette.addColorStop(1, 'rgba(8,4,20,.6)');
  ctx.fillStyle = vignette;
  ctx.fillRect(0, 0, OFFICE_WIDTH, OFFICE_HEIGHT);

  scene.texture.source.update();
}

export function drawOfficeFrame(
  scene: SceneCanvas,
  time: number,
  agentState: AgentState,
  solverState: SolverState,
  boardData: BoardData,
  chatMessage: string | null,
  chatUntil: number,
  agentMotion: AgentMotion,
) {
  drawFrame(scene, time, agentState, solverState, boardData, chatMessage, chatUntil, agentMotion);
}

export function createOfficeSceneTexture(): SceneCanvas {
  return createScene();
}
