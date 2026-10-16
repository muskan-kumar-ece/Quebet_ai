"use client";

import React, { useState, useRef, useMemo } from "react";
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Cpu,
  Zap,
  Activity,
  Radio,
  Sliders,
  Shield,
  Layers,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  EngineeringSubsystem,
  EngineeringSystemInterface,
  EngineeringPowerDomain,
  EngineeringSystemDependency,
} from "./types";

interface SystemCanvasProps {
  subsystems: EngineeringSubsystem[];
  interfaces: EngineeringSystemInterface[];
  powerDomains: EngineeringPowerDomain[];
  dependencies: EngineeringSystemDependency[];
  selectedSubsystemId: string | null;
  selectedInterfaceId: string | null;
  onSelectSubsystem: (id: string | null) => void;
  onSelectInterface: (id: string | null) => void;
  viewMode: "architecture" | "power" | "dependencies";
}

const TYPE_COLORS: Record<string, { bg: string; border: string; text: string; icon: any }> = {
  POWER: { bg: "bg-amber-950/40", border: "border-amber-600/80", text: "text-amber-400", icon: Zap },
  PROTECTION: { bg: "bg-red-950/40", border: "border-red-600/80", text: "text-red-400", icon: Shield },
  REGULATION: { bg: "bg-orange-950/40", border: "border-orange-600/80", text: "text-orange-400", icon: Sliders },
  PROCESSING: { bg: "bg-sky-950/40", border: "border-sky-600/80", text: "text-sky-400", icon: Cpu },
  SENSING: { bg: "bg-emerald-950/40", border: "border-emerald-600/80", text: "text-emerald-400", icon: Activity },
  COMMUNICATION: { bg: "bg-cyan-950/40", border: "border-cyan-600/80", text: "text-cyan-400", icon: Radio },
  STORAGE: { bg: "bg-indigo-950/40", border: "border-indigo-600/80", text: "text-indigo-400", icon: Layers },
  ACTUATION: { bg: "bg-purple-950/40", border: "border-purple-600/80", text: "text-purple-400", icon: Zap },
  USER_INTERFACE: { bg: "bg-pink-950/40", border: "border-pink-600/80", text: "text-pink-400", icon: Sliders },
};

const EDGE_COLORS: Record<string, string> = {
  POWER: "#f59e0b",
  GROUND: "#71717a",
  ANALOG_SIGNAL: "#10b981",
  DIGITAL_SIGNAL: "#3b82f6",
  CLOCK: "#ec4899",
  DATA: "#06b6d4",
  CONTROL: "#a855f7",
  COMMUNICATION: "#06b6d4",
  RF: "#ef4444",
  THERMAL: "#f97316",
  OTHER: "#a1a1aa",
};

export const SystemCanvas: React.FC<SystemCanvasProps> = ({
  subsystems,
  interfaces,
  powerDomains,
  dependencies,
  selectedSubsystemId,
  selectedInterfaceId,
  onSelectSubsystem,
  onSelectInterface,
  viewMode,
}) => {
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 50, y: 50 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  // Compute 2D node layout positions deterministically
  const nodePositions = useMemo(() => {
    const posMap: Record<string, { x: number; y: number; width: number; height: number }> = {};
    const colMap: Record<string, number> = {
      POWER: 0,
      PROTECTION: 0,
      REGULATION: 1,
      PROCESSING: 2,
      SENSING: 3,
      COMMUNICATION: 3,
      STORAGE: 2,
      ACTUATION: 3,
      USER_INTERFACE: 3,
    };

    const colCounts: Record<number, number> = { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0 };
    const colSpacing = 280;
    const rowSpacing = 160;

    subsystems.forEach((sub) => {
      const col = colMap[sub.subsystem_type] ?? 2;
      const row = colCounts[col] || 0;
      colCounts[col] = (colCounts[col] || 0) + 1;

      posMap[sub.id] = {
        x: 60 + col * colSpacing,
        y: 60 + row * rowSpacing,
        width: 220,
        height: 110,
      };
    });

    return posMap;
  }, [subsystems]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.target === containerRef.current || (e.target as HTMLElement).tagName === "svg") {
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  return (
    <div
      ref={containerRef}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      className="relative w-full h-full bg-zinc-950 overflow-hidden select-none cursor-grab active:cursor-grabbing"
      style={{
        backgroundImage: "radial-gradient(#27272a 1px, transparent 1px)",
        backgroundSize: "24px 24px",
      }}
    >
      {/* Zoom / Pan Controls */}
      <div className="absolute top-4 left-4 z-20 flex items-center gap-1.5 bg-zinc-900/90 border border-zinc-800 rounded-lg p-1 shadow-lg backdrop-blur">
        <Button
          size="sm"
          variant="ghost"
          className="h-7 w-7 p-0 text-zinc-400 hover:text-white"
          onClick={() => setScale((s) => Math.min(s + 0.15, 2.0))}
          title="Zoom In"
        >
          <ZoomIn className="w-4 h-4" />
        </Button>
        <span className="text-[11px] font-mono font-medium text-zinc-400 px-1">
          {Math.round(scale * 100)}%
        </span>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 w-7 p-0 text-zinc-400 hover:text-white"
          onClick={() => setScale((s) => Math.max(s - 0.15, 0.4))}
          title="Zoom Out"
        >
          <ZoomOut className="w-4 h-4" />
        </Button>
        <div className="h-4 w-px bg-zinc-800 mx-0.5" />
        <Button
          size="sm"
          variant="ghost"
          className="h-7 w-7 p-0 text-zinc-400 hover:text-white"
          onClick={() => {
            setScale(1);
            setPan({ x: 50, y: 50 });
          }}
          title="Reset View"
        >
          <Maximize2 className="w-3.5 h-3.5" />
        </Button>
      </div>

      {/* Semantic Legend */}
      <div className="absolute bottom-4 left-4 z-20 bg-zinc-900/90 border border-zinc-800 rounded-lg p-2.5 shadow-lg backdrop-blur flex items-center gap-4 text-[11px] text-zinc-400">
        <span className="font-semibold text-zinc-300">Interfaces:</span>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-amber-500" />
          <span>Power</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400" />
          <span>Data / Comm</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-purple-500" />
          <span>Control</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
          <span>Analog</span>
        </div>
      </div>

      {/* Interactive SVG Diagram */}
      <div
        className="w-full h-full origin-top-left"
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
          transition: isDragging ? "none" : "transform 0.05s ease-out",
        }}
      >
        <svg className="w-[3000px] h-[2000px] absolute inset-0 pointer-events-none">
          <defs>
            <marker
              id="arrow-generic"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#71717a" />
            </marker>
            {Object.entries(EDGE_COLORS).map(([type, color]) => (
              <marker
                key={type}
                id={`arrow-${type}`}
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill={color} />
              </marker>
            ))}
          </defs>

          {/* Render Interface Edges */}
          {interfaces.map((iface) => {
            const srcPos = nodePositions[iface.source_subsystem_id];
            const dstPos = nodePositions[iface.destination_subsystem_id];
            if (!srcPos || !dstPos) return null;

            const isSelected = selectedInterfaceId === iface.id;
            const x1 = srcPos.x + srcPos.width;
            const y1 = srcPos.y + srcPos.height / 2;
            const x2 = dstPos.x;
            const y2 = dstPos.y + dstPos.height / 2;
            const dx = Math.abs(x2 - x1) * 0.5;
            const pathData = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
            const strokeColor = EDGE_COLORS[iface.interface_type] || "#a1a1aa";

            return (
              <g
                key={iface.id}
                className="cursor-pointer pointer-events-auto"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectInterface(iface.id);
                  onSelectSubsystem(null);
                }}
              >
                <path
                  d={pathData}
                  fill="none"
                  stroke={isSelected ? "#ffffff" : strokeColor}
                  strokeWidth={isSelected ? 3 : 2}
                  strokeDasharray={iface.interface_type === "GROUND" ? "4 4" : undefined}
                  markerEnd={`url(#arrow-${iface.interface_type})`}
                  className="transition-all hover:opacity-100 opacity-80"
                />
                {/* Edge Label */}
                <text
                  x={(x1 + x2) / 2}
                  y={(y1 + y2) / 2 - 8}
                  fill={strokeColor}
                  fontSize="10"
                  fontFamily="monospace"
                  textAnchor="middle"
                  className="select-none font-bold"
                >
                  {iface.name}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Subsystem DOM Blocks */}
        {subsystems.map((sub) => {
          const pos = nodePositions[sub.id];
          if (!pos) return null;

          const isSelected = selectedSubsystemId === sub.id;
          const conf = TYPE_COLORS[sub.subsystem_type] || {
            bg: "bg-zinc-900/60",
            border: "border-zinc-700",
            text: "text-zinc-300",
            icon: Cpu,
          };
          const Icon = conf.icon;
          const childCount = subsystems.filter((s) => s.parent_subsystem_id === sub.id).length;

          return (
            <div
              key={sub.id}
              onClick={(e) => {
                e.stopPropagation();
                onSelectSubsystem(sub.id);
                onSelectInterface(null);
              }}
              style={{
                transform: `translate(${pos.x}px, ${pos.y}px)`,
                width: `${pos.width}px`,
                height: `${pos.height}px`,
              }}
              className={`absolute p-3 rounded-xl border transition-all cursor-pointer backdrop-blur shadow-md flex flex-col justify-between ${
                conf.bg
              } ${
                isSelected
                  ? "border-sky-400 ring-2 ring-sky-500/40 shadow-sky-950/50"
                  : `${conf.border} hover:border-zinc-500`
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <Icon className={`w-3.5 h-3.5 ${conf.text}`} />
                    <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-zinc-400">
                      {sub.subsystem_type}
                    </span>
                  </div>
                  <Badge variant="outline" className="text-[9px] font-mono px-1 py-0 h-4 border-zinc-700">
                    r{sub.revision}
                  </Badge>
                </div>
                <h3 className="text-xs font-bold text-zinc-100 tracking-tight line-clamp-1">
                  {sub.name}
                </h3>
                {sub.description && (
                  <p className="text-[10px] text-zinc-400 line-clamp-1 mt-0.5">{sub.description}</p>
                )}
              </div>

              <div className="flex items-center justify-between pt-1 border-t border-zinc-800/80 text-[10px] font-mono text-zinc-500">
                <span>{sub.circuit_id ? "Circuit Linked" : "Abstract Sub"}</span>
                {childCount > 0 && (
                  <span className="text-zinc-400 font-semibold">{childCount} sub-modules</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
