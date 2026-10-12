export type AgentState =
  | 'idle'
  | 'reading_board'
  | 'working'
  | 'waiting'
  | 'reporting';

export type SolverState = 'idle' | 'working' | 'done';

export type ParamStatus = 'defined' | 'undefined' | 'conflict';

export interface BoardField {
  key: string;
  label: string;
  value: string | number | null;
  status: ParamStatus;
  source: string;
}

export interface BoardData {
  division: string;
  title: string;
  lastUpdated: string;
  fields: {
    product_id: BoardField;
    on_hand_qty: BoardField;
    target_qty: BoardField;
    expected_outgoing_qty: BoardField;
    required_by: BoardField;
  };
}

export interface OfficeSceneState {
  agentState: AgentState;
  solverState: SolverState;
  boardData: BoardData;
  latestChatMessage: string | null;
  showSpeechBubble: boolean;
}

export interface GridPoint {
  gx: number;
  gy: number;
}

export interface IsometricPoint {
  x: number;
  y: number;
}

export interface LayoutWindow {
  id: string;
  wall: 'left_wall' | 'right_wall' | 'north_west' | 'north_east';
  gx?: number;
  gy?: number;
  width: number;
  height: number;
}

export interface LayoutAnchor {
  gx: number;
  gy: number;
  facing: 'north_west' | 'north_east' | 'south_west' | 'south_east';
}

export interface LayoutObject {
  id: string;
  sprite: string;
  gx: number;
  gy: number;
  width: number;
  height: number;
  interactive?: boolean;
  isFuture?: boolean;
  wallMounted?: boolean;
  wall?: 'north_west' | 'north_east';
  elevation?: number;
  label?: string;
}

export interface OfficeLayout {
  gridSize: {
    width: number;
    height: number;
  };
  tileSize: {
    width: number;
    height: number;
  };
  walls: {
    height: number;
    color: string;
    trimColor: string;
    skirtingColor: string;
    windows: LayoutWindow[];
  };
  anchors: Record<string, LayoutAnchor>;
  objects: LayoutObject[];
  settings: {
    showFutureDesks?: boolean;
    enableLightShafts?: boolean;
    enableDustParticles?: boolean;
  };
}

export interface OfficeSceneProps {
  onSelect?: (objectId: string) => void;
  layout?: OfficeLayout;
}
