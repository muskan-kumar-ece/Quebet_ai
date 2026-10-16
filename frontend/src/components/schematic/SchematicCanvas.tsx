"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";
import { useCircuitWorkspace } from "./useCircuitWorkspace";
import { ComponentSymbol, getPinCoordinates } from "./symbols";
import { getOrthogonalPath, computeJunctionDots, Point } from "./wireRouter";
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCw,
  Trash2,
  Grid,
  Magnet,
  RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface SchematicCanvasProps {
  onConnectionCreated?: (sourceCompId: string, sourcePin: string, targetCompId: string, targetPin: string) => Promise<void>;
  onConnectionDeleted?: (connectionId: string) => Promise<void>;
}

export const SchematicCanvas: React.FC<SchematicCanvasProps> = ({
  onConnectionCreated,
  onConnectionDeleted,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const {
    components,
    nets,
    connections,
    schematicObjects,
    selectedComponentId,
    selectedWireId,
    wireDrawingSource,
    gridEnabled,
    snapEnabled,
    gridSize,
    zoom,
    pan,
    setSelectedComponent,
    setSelectedWire,
    clearSelection,
    setGridEnabled,
    setSnapEnabled,
    setZoom,
    setPan,
    resetView,
    startWireDrawing,
    cancelWireDrawing,
    moveComponent,
    rotateComponent,
    deleteComponent,
    deleteConnection,
    undo,
    redo,
  } = useCircuitWorkspace();

  // Interaction States
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [draggingCompId, setDraggingCompId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [cursorPos, setCursorPos] = useState<Point>({ x: 0, y: 0 });

  // Convert client viewport coordinates to schematic Cartesian coordinates
  const screenToWorld = useCallback(
    (clientX: number, clientY: number): Point => {
      if (!svgRef.current) return { x: 0, y: 0 };
      const rect = svgRef.current.getBoundingClientRect();
      const rawX = (clientX - rect.left - pan.x) / zoom;
      const rawY = (clientY - rect.top - pan.y) / zoom;
      return {
        x: snapEnabled ? Math.round(rawX / gridSize) * gridSize : Math.round(rawX),
        y: snapEnabled ? Math.round(rawY / gridSize) * gridSize : Math.round(rawY),
      };
    },
    [pan, zoom, snapEnabled, gridSize]
  );

  // Wheel Zoom centered at mouse position
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    const newZoom = Math.max(0.25, Math.min(3.0, zoom * zoomFactor));

    if (svgRef.current) {
      const rect = svgRef.current.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      // Adjust pan to zoom towards mouse position
      const newPanX = mouseX - (mouseX - pan.x) * (newZoom / zoom);
      const newPanY = mouseY - (mouseY - pan.y) * (newZoom / zoom);

      setZoom(newZoom);
      setPan({ x: newPanX, y: newPanY });
    }
  };

  // Canvas Mouse Down
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 1 || (e.button === 0 && e.target === svgRef.current)) {
      // Middle click or clicking background initiates panning
      setIsPanning(true);
      setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
      clearSelection();
      if (wireDrawingSource) {
        cancelWireDrawing();
      }
    }
  };

  // Canvas Mouse Move
  const handleMouseMove = (e: React.MouseEvent) => {
    const worldPt = screenToWorld(e.clientX, e.clientY);
    setCursorPos(worldPt);

    if (isPanning) {
      setPan({ x: e.clientX - panStart.x, y: e.clientY - panStart.y });
    } else if (draggingCompId) {
      moveComponent(draggingCompId, worldPt.x - dragOffset.x, worldPt.y - dragOffset.y);
    }
  };

  // Canvas Mouse Up
  const handleMouseUp = () => {
    setIsPanning(false);
    setDraggingCompId(null);
  };

  // Pin Click for Wire Creation
  const handlePinClick = async (targetCompId: string, targetPinNumber: string) => {
    if (!wireDrawingSource) {
      // Start wire creation
      startWireDrawing(targetCompId, targetPinNumber);
    } else {
      // Attempt to complete connection
      if (
        wireDrawingSource.componentId === targetCompId &&
        wireDrawingSource.pinNumber === targetPinNumber
      ) {
        // Clicked the same pin -> cancel
        cancelWireDrawing();
        return;
      }

      if (onConnectionCreated) {
        await onConnectionCreated(
          wireDrawingSource.componentId,
          wireDrawingSource.pinNumber,
          targetCompId,
          targetPinNumber
        );
      }
      cancelWireDrawing();
    }
  };

  // Keyboard Shortcuts (Delete, Rotate, Undo, Redo, Cancel Wire)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.key === "Escape") {
        cancelWireDrawing();
        clearSelection();
      } else if (e.key === "Delete" || e.key === "Backspace") {
        if (selectedComponentId) {
          deleteComponent(selectedComponentId);
        } else if (selectedWireId && onConnectionDeleted) {
          onConnectionDeleted(selectedWireId);
          deleteConnection(selectedWireId);
        }
      } else if (e.key === "r" || e.key === "R") {
        if (selectedComponentId) {
          rotateComponent(selectedComponentId, 90);
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key === "z") {
        if (e.shiftKey) {
          redo();
        } else {
          undo();
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key === "y") {
        redo();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    selectedComponentId,
    selectedWireId,
    cancelWireDrawing,
    clearSelection,
    deleteComponent,
    deleteConnection,
    rotateComponent,
    undo,
    redo,
    onConnectionDeleted,
  ]);

  // Compute Wires from persisted Connections & Nets
  const netMap = new Map(nets.map((n) => [n.id, n]));
  const compMap = new Map(components.map((c) => [c.id, c]));
  const schemMap = new Map(schematicObjects.map((s) => [s.component_id, s]));

  // Group connections by Net
  const connectionsByNet = new Map<string, typeof connections>();
  connections.forEach((conn) => {
    const list = connectionsByNet.get(conn.net_id) || [];
    list.push(conn);
    connectionsByNet.set(conn.net_id, list);
  });

  // Calculate Wire Segments and Junction Dots
  interface ComputedWire {
    id: string;
    netId: string;
    netName: string;
    netType: string;
    path: string;
    from: Point;
    to: Point;
  }

  const computedWires: ComputedWire[] = [];
  const connectionPoints: Point[] = [];

  connectionsByNet.forEach((connList, netId) => {
    const net = netMap.get(netId);
    const netName = net?.name || "NET";
    const netType = net?.net_type || "signal";

    if (connList.length >= 2) {
      // Connect first pin as star-root or sequential bus
      const rootConn = connList[0];
      if (!rootConn) return;
      const rootComp = compMap.get(rootConn.component_id);
      const rootSchem = schemMap.get(rootConn.component_id);

      if (rootComp) {
        const rootPos = getPinCoordinates(rootComp, rootConn.pin_number, rootSchem);
        connectionPoints.push(rootPos);

        for (let i = 1; i < connList.length; i++) {
          const targetConn = connList[i];
          if (!targetConn) continue;
          const targetComp = compMap.get(targetConn.component_id);
          const targetSchem = schemMap.get(targetConn.component_id);

          if (targetComp) {
            const targetPos = getPinCoordinates(targetComp, targetConn.pin_number, targetSchem);
            connectionPoints.push(targetPos);
            computedWires.push({
              id: `${rootConn.id}-${targetConn.id}`,
              netId,
              netName,
              netType,
              path: getOrthogonalPath(rootPos, targetPos),
              from: rootPos,
              to: targetPos,
            });
          }
        }
      }
    }
  });

  const junctionDots = computeJunctionDots(connectionPoints);

  // Wire Preview during interactive drawing
  let previewWirePath: string | null = null;
  if (wireDrawingSource) {
    const sourceComp = compMap.get(wireDrawingSource.componentId);
    const sourceSchem = schemMap.get(wireDrawingSource.componentId);
    if (sourceComp) {
      const sourcePt = getPinCoordinates(sourceComp, wireDrawingSource.pinNumber, sourceSchem);
      previewWirePath = getOrthogonalPath(sourcePt, cursorPos);
    }
  }

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full min-h-[600px] bg-[#090d16] select-none overflow-hidden rounded-xl border border-zinc-800"
    >
      {/* Floating Canvas Action Toolbar */}
      <div className="absolute top-4 left-4 z-20 flex items-center gap-1.5 p-1.5 bg-zinc-900/90 border border-zinc-800 rounded-lg backdrop-blur shadow-xl">
        <Button
          size="sm"
          variant="outline"
          className="h-8 w-8 p-0 border-zinc-700 bg-zinc-800/80 hover:bg-zinc-700"
          onClick={() => setZoom((z) => Math.min(3.0, z + 0.2))}
          title="Zoom In"
        >
          <ZoomIn className="w-4 h-4 text-zinc-300" />
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="h-8 w-8 p-0 border-zinc-700 bg-zinc-800/80 hover:bg-zinc-700"
          onClick={() => setZoom((z) => Math.max(0.3, z - 0.2))}
          title="Zoom Out"
        >
          <ZoomOut className="w-4 h-4 text-zinc-300" />
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="h-8 w-8 p-0 border-zinc-700 bg-zinc-800/80 hover:bg-zinc-700"
          onClick={resetView}
          title="Reset View"
        >
          <Maximize2 className="w-4 h-4 text-zinc-300" />
        </Button>

        <div className="w-[1px] h-5 bg-zinc-700 mx-1" />

        <Button
          size="sm"
          variant="outline"
          className={`h-8 w-8 p-0 border-zinc-700 ${
            gridEnabled ? "bg-sky-950/60 border-sky-600 text-sky-400" : "bg-zinc-800/80 text-zinc-400"
          }`}
          onClick={() => setGridEnabled(!gridEnabled)}
          title="Toggle Grid"
        >
          <Grid className="w-4 h-4" />
        </Button>
        <Button
          size="sm"
          variant="outline"
          className={`h-8 w-8 p-0 border-zinc-700 ${
            snapEnabled ? "bg-sky-950/60 border-sky-600 text-sky-400" : "bg-zinc-800/80 text-zinc-400"
          }`}
          onClick={() => setSnapEnabled(!snapEnabled)}
          title="Snap to Grid"
        >
          <Magnet className="w-4 h-4" />
        </Button>

        <div className="w-[1px] h-5 bg-zinc-700 mx-1" />

        {selectedComponentId && (
          <>
            <Button
              size="sm"
              variant="outline"
              className="h-8 w-8 p-0 border-zinc-700 bg-zinc-800/80 hover:bg-zinc-700"
              onClick={() => rotateComponent(selectedComponentId, 90)}
              title="Rotate Component (R)"
            >
              <RotateCw className="w-4 h-4 text-zinc-300" />
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-8 w-8 p-0 border-zinc-700 bg-red-950/40 border-red-800 hover:bg-red-900/50"
              onClick={() => deleteComponent(selectedComponentId)}
              title="Delete Component"
            >
              <Trash2 className="w-4 h-4 text-red-400" />
            </Button>
          </>
        )}
      </div>

      {/* Wire Drawing Banner */}
      {wireDrawingSource && (
        <div className="absolute top-4 right-4 z-20 flex items-center gap-3 px-3 py-1.5 bg-sky-950/90 border border-sky-600 rounded-lg text-xs text-sky-200 shadow-xl backdrop-blur">
          <span className="w-2 h-2 rounded-full bg-sky-400 animate-ping" />
          <span>Click target pin to complete electrical net. Press ESC to cancel.</span>
          <Button
            size="sm"
            variant="ghost"
            className="h-6 px-2 text-xs text-zinc-400 hover:text-white"
            onClick={cancelWireDrawing}
          >
            Cancel
          </Button>
        </div>
      )}

      {/* Interactive SVG Canvas */}
      <svg
        ref={svgRef}
        className="w-full h-full cursor-default"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onWheel={handleWheel}
      >
        <defs>
          {/* Engineering Dot Grid Pattern */}
          <pattern
            id="dot-grid"
            width={gridSize * zoom}
            height={gridSize * zoom}
            patternUnits="userSpaceOnUse"
          >
            <circle
              cx={(gridSize * zoom) / 2}
              cy={(gridSize * zoom) / 2}
              r={1 * Math.min(zoom, 1.5)}
              fill="rgba(148, 163, 184, 0.18)"
            />
          </pattern>
        </defs>

        {/* Grid Background */}
        {gridEnabled && (
          <rect
            x="0"
            y="0"
            width="100%"
            height="100%"
            fill="url(#dot-grid)"
            style={{
              transform: `translate(${pan.x % (gridSize * zoom)}px, ${pan.y % (gridSize * zoom)}px)`,
            }}
          />
        )}

        {/* Global World Transform (Pan + Zoom) */}
        <g transform={`matrix(${zoom} 0 0 ${zoom} ${pan.x} ${pan.y})`}>
          {/* 1. Electrical Wires */}
          {computedWires.map((wire) => {
            const isSelected = selectedWireId === wire.id;
            const wireColor =
              wire.netType === "power"
                ? "#ef4444"
                : wire.netType === "ground"
                ? "#10b981"
                : isSelected
                ? "#38bdf8"
                : "#0284c7";

            return (
              <g
                key={wire.id}
                className="cursor-pointer group"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedWire(wire.id);
                }}
              >
                {/* Thick invisible hit target */}
                <path d={wire.path} fill="none" stroke="transparent" strokeWidth="12" />
                {/* Visual Wire */}
                <path
                  d={wire.path}
                  fill="none"
                  stroke={wireColor}
                  strokeWidth={isSelected ? "3" : "2"}
                  strokeLinecap="round"
                  className="transition-colors group-hover:stroke-sky-400"
                />
                {/* Net Label along wire */}
                <text
                  x={(wire.from.x + wire.to.x) / 2}
                  y={(wire.from.y + wire.to.y) / 2 - 6}
                  fill="#94a3b8"
                  fontSize="9"
                  fontFamily="monospace"
                  textAnchor="middle"
                  className="pointer-events-none"
                >
                  {wire.netName}
                </text>
              </g>
            );
          })}

          {/* 2. Solder Junction Dots */}
          {junctionDots.map((pt, idx) => (
            <circle
              key={`junc-${idx}`}
              cx={pt.x}
              cy={pt.y}
              r="4"
              fill="#38bdf8"
              stroke="#0f172a"
              strokeWidth="1.5"
            />
          ))}

          {/* 3. Rubberband Preview Wire */}
          {previewWirePath && (
            <path
              d={previewWirePath}
              fill="none"
              stroke="#38bdf8"
              strokeWidth="2.5"
              strokeDasharray="4 4"
              className="animate-pulse pointer-events-none"
            />
          )}

          {/* 4. Schematic Components */}
          {components.map((comp) => {
            const schemObj = schemMap.get(comp.id) || {
              id: `so-${comp.id}`,
              circuit_id: comp.circuit_id,
              object_type: "symbol" as const,
              component_id: comp.id,
              pos_x: 100,
              pos_y: 100,
              rotation: 0,
            };

            const isSelected = selectedComponentId === comp.id;

            return (
              <g
                key={comp.id}
                onMouseDown={(e) => {
                  e.stopPropagation();
                  setSelectedComponent(comp.id);
                  setDraggingCompId(comp.id);
                  const worldPt = screenToWorld(e.clientX, e.clientY);
                  setDragOffset({
                    x: worldPt.x - schemObj.pos_x,
                    y: worldPt.y - schemObj.pos_y,
                  });
                }}
              >
                <ComponentSymbol
                  component={comp}
                  schemObj={schemObj}
                  isSelected={isSelected}
                  onPinClick={(pinNum, pinName) => handlePinClick(comp.id, pinNum)}
                  activeWireSourcePin={wireDrawingSource}
                />
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
};
