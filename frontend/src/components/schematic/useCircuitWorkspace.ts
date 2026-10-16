import { create } from "zustand";
import type {
  SchematicComponent,
  SchematicNet,
  SchematicConnection,
  SchematicObject,
  AutosaveStatus,
} from "./types";

interface HistorySnapshot {
  components: SchematicComponent[];
  nets: SchematicNet[];
  connections: SchematicConnection[];
  schematicObjects: SchematicObject[];
}

interface CircuitWorkspaceState {
  circuitId: string | null;
  version: number;
  circuitName: string;
  validationStatus: string;

  components: SchematicComponent[];
  nets: SchematicNet[];
  connections: SchematicConnection[];
  schematicObjects: SchematicObject[];
  assumptions: any[];

  selectedComponentId: string | null;
  selectedNetId: string | null;
  selectedWireId: string | null;

  wireDrawingSource: { componentId: string; pinNumber: string; pinName?: string } | null;

  gridEnabled: boolean;
  snapEnabled: boolean;
  gridSize: number;
  zoom: number;
  pan: { x: number; y: number };

  autosaveStatus: AutosaveStatus;
  lastSavedAt: Date | null;

  // History for Undo/Redo
  past: HistorySnapshot[];
  future: HistorySnapshot[];

  // Actions
  initCircuit: (data: any) => void;
  setSelectedComponent: (id: string | null) => void;
  setSelectedNet: (id: string | null) => void;
  setSelectedWire: (id: string | null) => void;
  clearSelection: () => void;

  setGridEnabled: (enabled: boolean) => void;
  setSnapEnabled: (enabled: boolean) => void;
  setGridSize: (size: number) => void;
  setZoom: (zoom: number | ((prev: number) => number)) => void;
  setPan: (pan: { x: number; y: number } | ((prev: { x: number; y: number }) => { x: number; y: number })) => void;
  resetView: () => void;

  startWireDrawing: (componentId: string, pinNumber: string, pinName?: string) => void;
  cancelWireDrawing: () => void;

  moveComponent: (id: string, posX: number, posY: number) => void;
  rotateComponent: (id: string, delta?: number) => void;
  updateComponentProperty: (id: string, updates: Partial<SchematicComponent>) => void;
  deleteComponent: (id: string) => void;
  deleteConnection: (id: string) => void;
  deleteNet: (id: string) => void;

  addNet: (net: SchematicNet) => void;
  addConnection: (conn: SchematicConnection) => void;

  setAutosaveStatus: (status: AutosaveStatus) => void;

  undo: () => void;
  redo: () => void;
}

export const useCircuitWorkspace = create<CircuitWorkspaceState>((set, get) => {
  const recordHistory = () => {
    const { components, nets, connections, schematicObjects, past } = get();
    const snapshot: HistorySnapshot = {
      components: JSON.parse(JSON.stringify(components)),
      nets: JSON.parse(JSON.stringify(nets)),
      connections: JSON.parse(JSON.stringify(connections)),
      schematicObjects: JSON.parse(JSON.stringify(schematicObjects)),
    };
    return {
      past: [...past.slice(-20), snapshot],
      future: [],
      autosaveStatus: "unsaved" as AutosaveStatus,
    };
  };

  return {
    circuitId: null,
    version: 1,
    circuitName: "Untitled Circuit",
    validationStatus: "DRAFT",

    components: [],
    nets: [],
    connections: [],
    schematicObjects: [],
    assumptions: [],

    selectedComponentId: null,
    selectedNetId: null,
    selectedWireId: null,

    wireDrawingSource: null,

    gridEnabled: true,
    snapEnabled: true,
    gridSize: 20,
    zoom: 1.0,
    pan: { x: 80, y: 80 },

    autosaveStatus: "saved",
    lastSavedAt: new Date(),

    past: [],
    future: [],

    initCircuit: (data: any) => {
      set({
        circuitId: data.id,
        version: data.version || 1,
        circuitName: data.name || "Untitled Circuit",
        validationStatus: data.validation_status || "DRAFT",
        components: data.components || [],
        nets: data.nets || [],
        connections: data.connections || [],
        schematicObjects: data.schematic_objects || [],
        assumptions: data.assumptions || [],
        selectedComponentId: data.components?.[0]?.id || null,
        selectedNetId: null,
        selectedWireId: null,
        past: [],
        future: [],
        autosaveStatus: "saved",
      });
    },

    setSelectedComponent: (id) =>
      set({ selectedComponentId: id, selectedNetId: null, selectedWireId: null }),

    setSelectedNet: (id) =>
      set({ selectedNetId: id, selectedComponentId: null, selectedWireId: null }),

    setSelectedWire: (id) =>
      set({ selectedWireId: id, selectedComponentId: null, selectedNetId: null }),

    clearSelection: () =>
      set({ selectedComponentId: null, selectedNetId: null, selectedWireId: null }),

    setGridEnabled: (gridEnabled) => set({ gridEnabled }),
    setSnapEnabled: (snapEnabled) => set({ snapEnabled }),
    setGridSize: (gridSize) => set({ gridSize }),

    setZoom: (zoom) =>
      set((state) => ({
        zoom: typeof zoom === "function" ? Math.max(0.2, Math.min(3.0, zoom(state.zoom))) : Math.max(0.2, Math.min(3.0, zoom)),
      })),

    setPan: (pan) =>
      set((state) => ({
        pan: typeof pan === "function" ? pan(state.pan) : pan,
      })),

    resetView: () => set({ zoom: 1.0, pan: { x: 80, y: 80 } }),

    startWireDrawing: (componentId, pinNumber, pinName) =>
      set({ wireDrawingSource: { componentId, pinNumber, pinName } }),

    cancelWireDrawing: () => set({ wireDrawingSource: null }),

    moveComponent: (id, posX, posY) => {
      const { snapEnabled, gridSize, schematicObjects } = get();
      const finalX = snapEnabled ? Math.round(posX / gridSize) * gridSize : Math.round(posX);
      const finalY = snapEnabled ? Math.round(posY / gridSize) * gridSize : Math.round(posY);

      set({
        ...recordHistory(),
        schematicObjects: schematicObjects.map((obj) =>
          obj.component_id === id ? { ...obj, pos_x: finalX, pos_y: finalY } : obj
        ),
      });
    },

    rotateComponent: (id, delta = 90) => {
      const { schematicObjects } = get();
      set({
        ...recordHistory(),
        schematicObjects: schematicObjects.map((obj) =>
          obj.component_id === id ? { ...obj, rotation: (obj.rotation + delta) % 360 } : obj
        ),
      });
    },

    updateComponentProperty: (id, updates) => {
      const { components } = get();
      set({
        ...recordHistory(),
        components: components.map((c) => (c.id === id ? { ...c, ...updates } : c)),
      });
    },

    deleteComponent: (id) => {
      const { components, connections, schematicObjects } = get();
      set({
        ...recordHistory(),
        components: components.filter((c) => c.id !== id),
        connections: connections.filter((conn) => conn.component_id !== id),
        schematicObjects: schematicObjects.filter((o) => o.component_id !== id),
        selectedComponentId: null,
      });
    },

    deleteConnection: (id) => {
      const { connections } = get();
      set({
        ...recordHistory(),
        connections: connections.filter((conn) => conn.id !== id),
        selectedWireId: null,
      });
    },

    deleteNet: (id) => {
      const { nets, connections } = get();
      set({
        ...recordHistory(),
        nets: nets.filter((n) => n.id !== id),
        connections: connections.filter((conn) => conn.net_id !== id),
        selectedNetId: null,
      });
    },

    addNet: (net) => {
      set((state) => ({
        ...recordHistory(),
        nets: [...state.nets, net],
      }));
    },

    addConnection: (conn) => {
      set((state) => ({
        ...recordHistory(),
        connections: [...state.connections, conn],
        wireDrawingSource: null,
      }));
    },

    setAutosaveStatus: (autosaveStatus) =>
      set({
        autosaveStatus,
        lastSavedAt: autosaveStatus === "saved" ? new Date() : get().lastSavedAt,
      }),

    undo: () => {
      const { past, future, components, nets, connections, schematicObjects } = get();
      if (past.length === 0) return;

      const previous = past[past.length - 1];
      if (!previous) return;
      const newPast = past.slice(0, past.length - 1);
      const currentSnapshot: HistorySnapshot = { components, nets, connections, schematicObjects };

      set({
        components: previous.components,
        nets: previous.nets,
        connections: previous.connections,
        schematicObjects: previous.schematicObjects,
        past: newPast,
        future: [currentSnapshot, ...future],
        autosaveStatus: "unsaved",
      });
    },

    redo: () => {
      const { past, future, components, nets, connections, schematicObjects } = get();
      if (future.length === 0) return;

      const next = future[0];
      if (!next) return;
      const newFuture = future.slice(1);
      const currentSnapshot: HistorySnapshot = { components, nets, connections, schematicObjects };

      set({
        components: next.components,
        nets: next.nets,
        connections: next.connections,
        schematicObjects: next.schematicObjects,
        past: [...past, currentSnapshot],
        future: newFuture,
        autosaveStatus: "unsaved",
      });
    },
  };
});
