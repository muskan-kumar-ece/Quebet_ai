"use client";

import React, { useState, useMemo } from "react";
import {
  Layers,
  Cpu,
  Zap,
  ArrowRight,
  ShieldAlert,
  Search,
  ChevronRight,
  ChevronDown,
  FileCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  Sliders,
  FolderTree,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  EngineeringSubsystem,
  EngineeringSystemInterface,
  EngineeringPowerDomain,
  EngineeringOperatingMode,
  EngineeringSystemRequirement,
} from "./types";

interface SystemTreeProps {
  subsystems: EngineeringSubsystem[];
  interfaces: EngineeringSystemInterface[];
  powerDomains: EngineeringPowerDomain[];
  operatingModes: EngineeringOperatingMode[];
  requirements: EngineeringSystemRequirement[];
  selectedSubsystemId?: string | null;
  selectedInterfaceId?: string | null;
  selectedPowerDomainId?: string | null;
  selectedRequirementId?: string | null;
  onSelectSubsystem?: (subsystem: EngineeringSubsystem) => void;
  onSelectInterface?: (iface: EngineeringSystemInterface) => void;
  onSelectPowerDomain?: (domain: EngineeringPowerDomain) => void;
  onSelectRequirement?: (req: EngineeringSystemRequirement) => void;
  onAddSubsystem?: () => void;
}

type TabType = "subsystems" | "interfaces" | "power" | "modes" | "requirements";

export const SystemTree: React.FC<SystemTreeProps> = ({
  subsystems,
  interfaces,
  powerDomains,
  operatingModes,
  requirements,
  selectedSubsystemId,
  selectedInterfaceId,
  selectedPowerDomainId,
  selectedRequirementId,
  onSelectSubsystem,
  onSelectInterface,
  onSelectPowerDomain,
  onSelectRequirement,
  onAddSubsystem,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>("subsystems");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});

  const toggleExpand = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedNodes((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  // Build tree hierarchy: root nodes (parent_subsystem_id is null/undefined) and children map
  const { rootNodes, childrenMap } = useMemo(() => {
    const roots: EngineeringSubsystem[] = [];
    const map: Record<string, EngineeringSubsystem[]> = {};

    for (const sub of subsystems) {
      if (!sub.parent_subsystem_id) {
        roots.push(sub);
      } else {
        const parentId = sub.parent_subsystem_id;
        if (!map[parentId]) {
          map[parentId] = [];
        }
        map[parentId]!.push(sub);
      }
    }
    return { rootNodes: roots, childrenMap: map };
  }, [subsystems]);

  const filteredSubsystems = useMemo(() => {
    if (!searchQuery.trim()) return subsystems;
    const q = searchQuery.toLowerCase();
    return subsystems.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.subsystem_type.toLowerCase().includes(q) ||
        (s.description && s.description.toLowerCase().includes(q))
    );
  }, [subsystems, searchQuery]);

  const filteredInterfaces = useMemo(() => {
    if (!searchQuery.trim()) return interfaces;
    const q = searchQuery.toLowerCase();
    return interfaces.filter(
      (i) =>
        i.name.toLowerCase().includes(q) ||
        i.interface_type.toLowerCase().includes(q) ||
        (i.description && i.description.toLowerCase().includes(q))
    );
  }, [interfaces, searchQuery]);

  const filteredPowerDomains = useMemo(() => {
    if (!searchQuery.trim()) return powerDomains;
    const q = searchQuery.toLowerCase();
    return powerDomains.filter((p) => p.name.toLowerCase().includes(q));
  }, [powerDomains, searchQuery]);

  const filteredRequirements = useMemo(() => {
    if (!searchQuery.trim()) return requirements;
    const q = searchQuery.toLowerCase();
    return requirements.filter(
      (r) =>
        r.code.toLowerCase().includes(q) ||
        r.title.toLowerCase().includes(q) ||
        r.status.toLowerCase().includes(q)
    );
  }, [requirements, searchQuery]);

  const renderSubsystemNode = (sub: EngineeringSubsystem, depth = 0) => {
    const children = childrenMap[sub.id] || [];
    const hasChildren = children.length > 0;
    const isExpanded = expandedNodes[sub.id] ?? true;
    const isSelected = selectedSubsystemId === sub.id;

    return (
      <div key={sub.id} className="flex flex-col">
        <div
          onClick={() => onSelectSubsystem?.(sub)}
          style={{ paddingLeft: `${depth * 14 + 8}px` }}
          className={`flex items-center justify-between py-1.5 pr-2 rounded text-xs cursor-pointer transition-colors ${
            isSelected
              ? "bg-sky-950/60 text-sky-200 border border-sky-800/80 font-medium"
              : "text-zinc-300 hover:bg-zinc-800/50 hover:text-zinc-100"
          }`}
        >
          <div className="flex items-center gap-1.5 truncate">
            {hasChildren ? (
              <button
                type="button"
                onClick={(e) => toggleExpand(sub.id, e)}
                className="p-0.5 text-zinc-400 hover:text-zinc-200"
              >
                {isExpanded ? (
                  <ChevronDown className="w-3.5 h-3.5" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5" />
                )}
              </button>
            ) : (
              <span className="w-4" />
            )}
            <Cpu className="w-3.5 h-3.5 text-sky-400 shrink-0" />
            <span className="truncate">{sub.name}</span>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <span className="text-[10px] px-1 py-0.2 rounded font-mono uppercase bg-zinc-800 text-zinc-400">
              {sub.subsystem_type}
            </span>
            {sub.circuit_id && (
              <span className="text-[9px] px-1 py-0.2 rounded bg-purple-950/80 text-purple-300 border border-purple-800/50">
                CIRCUIT
              </span>
            )}
          </div>
        </div>

        {hasChildren && isExpanded && (
          <div className="flex flex-col">
            {children.map((child) => renderSubsystemNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  const getRequirementBadge = (status: string) => {
    switch (status) {
      case "SUPPORTED":
        return <Badge className="text-[10px] bg-emerald-950/80 text-emerald-400 border border-emerald-800">SUPPORTED</Badge>;
      case "VIOLATED":
        return <Badge className="text-[10px] bg-red-950/80 text-red-400 border border-red-800">VIOLATED</Badge>;
      case "PARTIALLY_SUPPORTED":
        return <Badge className="text-[10px] bg-amber-950/80 text-amber-400 border border-amber-800">PARTIAL</Badge>;
      default:
        return <Badge className="text-[10px] bg-zinc-800 text-zinc-400 border border-zinc-700">UNKNOWN</Badge>;
    }
  };

  return (
    <aside className="w-80 border-r border-zinc-800/80 bg-zinc-900/40 flex flex-col shrink-0 select-none">
      {/* Top Search Filter */}
      <div className="p-3 border-b border-zinc-800/80">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter system elements..."
            className="h-8 pl-8 pr-2 text-xs bg-zinc-950/80 border-zinc-800 text-zinc-200 placeholder:text-zinc-600 focus-visible:ring-sky-500"
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="grid grid-cols-5 p-1 border-b border-zinc-800/80 bg-zinc-900/80 text-[11px] font-medium">
        <button
          onClick={() => setActiveTab("subsystems")}
          className={`py-1.5 rounded flex flex-col items-center gap-0.5 ${
            activeTab === "subsystems"
              ? "bg-zinc-800 text-sky-400 font-semibold"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
          title="Subsystems"
        >
          <FolderTree className="w-3.5 h-3.5" />
          <span>Subs ({subsystems.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("interfaces")}
          className={`py-1.5 rounded flex flex-col items-center gap-0.5 ${
            activeTab === "interfaces"
              ? "bg-zinc-800 text-emerald-400 font-semibold"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
          title="System Interfaces"
        >
          <ArrowRight className="w-3.5 h-3.5" />
          <span>Ifaces ({interfaces.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("power")}
          className={`py-1.5 rounded flex flex-col items-center gap-0.5 ${
            activeTab === "power"
              ? "bg-zinc-800 text-amber-400 font-semibold"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
          title="Power Domains"
        >
          <Zap className="w-3.5 h-3.5" />
          <span>Rails ({powerDomains.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("modes")}
          className={`py-1.5 rounded flex flex-col items-center gap-0.5 ${
            activeTab === "modes"
              ? "bg-zinc-800 text-purple-400 font-semibold"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
          title="Operating Modes"
        >
          <Sliders className="w-3.5 h-3.5" />
          <span>Modes ({operatingModes.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("requirements")}
          className={`py-1.5 rounded flex flex-col items-center gap-0.5 ${
            activeTab === "requirements"
              ? "bg-zinc-800 text-cyan-400 font-semibold"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
          title="System Requirements"
        >
          <FileCheck className="w-3.5 h-3.5" />
          <span>Reqs ({requirements.length})</span>
        </button>
      </div>

      {/* Main List Area */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {/* Subsystems Tree View */}
        {activeTab === "subsystems" && (
          <div className="space-y-1">
            {searchQuery.trim() ? (
              filteredSubsystems.map((sub) => renderSubsystemNode(sub, 0))
            ) : (
              rootNodes.map((sub) => renderSubsystemNode(sub, 0))
            )}
            {subsystems.length === 0 && (
              <div className="text-center py-8 text-zinc-600 text-xs">
                No subsystems defined.
              </div>
            )}
          </div>
        )}

        {/* Interfaces List */}
        {activeTab === "interfaces" && (
          <div className="space-y-1">
            {filteredInterfaces.map((iface) => {
              const isSelected = selectedInterfaceId === iface.id;
              const srcSub = subsystems.find((s) => s.id === iface.source_subsystem_id);
              const dstSub = subsystems.find((s) => s.id === iface.destination_subsystem_id);

              return (
                <div
                  key={iface.id}
                  onClick={() => onSelectInterface?.(iface)}
                  className={`p-2 rounded text-xs cursor-pointer border transition-colors ${
                    isSelected
                      ? "bg-emerald-950/40 border-emerald-800/80 text-emerald-200"
                      : "bg-zinc-950/50 border-zinc-800/60 text-zinc-300 hover:bg-zinc-800/40"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium truncate">{iface.name}</span>
                    <Badge variant="outline" className="text-[10px] font-mono border-zinc-700 text-zinc-400">
                      {iface.interface_type}
                    </Badge>
                  </div>
                  <div className="text-[11px] text-zinc-500 flex items-center gap-1 truncate font-mono">
                    <span className="truncate">{srcSub?.name || "SRC"}</span>
                    <ArrowRight className="w-3 h-3 shrink-0" />
                    <span className="truncate">{dstSub?.name || "DST"}</span>
                  </div>
                </div>
              );
            })}
            {interfaces.length === 0 && (
              <div className="text-center py-8 text-zinc-600 text-xs">
                No interfaces defined.
              </div>
            )}
          </div>
        )}

        {/* Power Domains List */}
        {activeTab === "power" && (
          <div className="space-y-1">
            {filteredPowerDomains.map((domain) => {
              const isSelected = selectedPowerDomainId === domain.id;
              const srcSub = subsystems.find((s) => s.id === domain.source_subsystem_id);

              return (
                <div
                  key={domain.id}
                  onClick={() => onSelectPowerDomain?.(domain)}
                  className={`p-2 rounded text-xs cursor-pointer border transition-colors ${
                    isSelected
                      ? "bg-amber-950/40 border-amber-800/80 text-amber-200"
                      : "bg-zinc-950/50 border-zinc-800/60 text-zinc-300 hover:bg-zinc-800/40"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-1.5">
                      <Zap className="w-3.5 h-3.5 text-amber-400" />
                      <span className="font-medium">{domain.name}</span>
                    </div>
                    <span className="text-[11px] font-mono text-amber-300 font-semibold">
                      {domain.nominal_voltage}V
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-zinc-500 font-mono">
                    <span>Source: {srcSub?.name || "External"}</span>
                    <span>Cap: {domain.current_capacity_a ?? "?"}A</span>
                  </div>
                </div>
              );
            })}
            {powerDomains.length === 0 && (
              <div className="text-center py-8 text-zinc-600 text-xs">
                No power domains configured.
              </div>
            )}
          </div>
        )}

        {/* Operating Modes List */}
        {activeTab === "modes" && (
          <div className="space-y-1.5">
            {operatingModes.map((mode) => (
              <div
                key={mode.id}
                className="p-2.5 rounded text-xs border bg-zinc-950/50 border-zinc-800/60 text-zinc-300"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <Sliders className="w-3.5 h-3.5 text-purple-400" />
                    <span className="font-semibold text-zinc-200">{mode.name}</span>
                  </div>
                  <Badge variant="outline" className="text-[10px] text-purple-400 border-purple-800">
                    {mode.active_subsystem_ids.length} Active Subs
                  </Badge>
                </div>
                {mode.description && (
                  <p className="text-[11px] text-zinc-500 line-clamp-2 mb-1.5">
                    {mode.description}
                  </p>
                )}
                <div className="text-[10px] text-zinc-500 font-mono">
                  Rails: {mode.expected_power_domain_ids.length} | Interfaces: {mode.relevant_interface_ids.length}
                </div>
              </div>
            ))}
            {operatingModes.length === 0 && (
              <div className="text-center py-8 text-zinc-600 text-xs">
                No operating modes configured.
              </div>
            )}
          </div>
        )}

        {/* Requirements List */}
        {activeTab === "requirements" && (
          <div className="space-y-1.5">
            {filteredRequirements.map((req) => {
              const isSelected = selectedRequirementId === req.id;
              return (
                <div
                  key={req.id}
                  onClick={() => onSelectRequirement?.(req)}
                  className={`p-2.5 rounded text-xs cursor-pointer border transition-colors ${
                    isSelected
                      ? "bg-cyan-950/40 border-cyan-800/80 text-cyan-200"
                      : "bg-zinc-950/50 border-zinc-800/60 text-zinc-300 hover:bg-zinc-800/40"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-cyan-400 font-bold">{req.code}</span>
                    {getRequirementBadge(req.status)}
                  </div>
                  <div className="font-medium text-zinc-200 truncate mb-1">
                    {req.title}
                  </div>
                  <div className="text-[11px] text-zinc-500 line-clamp-2">
                    {req.description}
                  </div>
                </div>
              );
            })}
            {requirements.length === 0 && (
              <div className="text-center py-8 text-zinc-600 text-xs">
                No system requirements recorded.
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
