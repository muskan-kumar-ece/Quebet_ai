"use client";

import React, { useState } from "react";
import {
  Cpu,
  Zap,
  ArrowRight,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  FileCheck,
  ChevronRight,
  Sliders,
  ExternalLink,
  Code,
  Info,
  GitBranch,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  EngineeringSubsystem,
  EngineeringSystemInterface,
  EngineeringPowerDomain,
  EngineeringSystemRequirement,
  EngineeringSystemFinding,
  EngineeringSystemAnalysis,
  EngineeringSystemDependency,
} from "./types";

interface SystemInspectorProps {
  subsystems: EngineeringSubsystem[];
  interfaces: EngineeringSystemInterface[];
  powerDomains: EngineeringPowerDomain[];
  dependencies: EngineeringSystemDependency[];
  requirements: EngineeringSystemRequirement[];
  latestAnalysis?: EngineeringSystemAnalysis | null;
  selectedSubsystem?: EngineeringSubsystem | null;
  selectedInterface?: EngineeringSystemInterface | null;
  selectedPowerDomain?: EngineeringPowerDomain | null;
  selectedRequirement?: EngineeringSystemRequirement | null;
  onNavigateSubsystem?: (id: string) => void;
  onNavigateInterface?: (id: string) => void;
  onNavigateCircuit?: (circuitId: string) => void;
  onClearSelection?: () => void;
}

export const SystemInspector: React.FC<SystemInspectorProps> = ({
  subsystems,
  interfaces,
  powerDomains,
  dependencies,
  requirements,
  latestAnalysis,
  selectedSubsystem,
  selectedInterface,
  selectedPowerDomain,
  selectedRequirement,
  onNavigateSubsystem,
  onNavigateInterface,
  onNavigateCircuit,
  onClearSelection,
}) => {
  const [activeTab, setActiveTab] = useState<"details" | "findings" | "traceability">("details");

  const findings = latestAnalysis?.findings || [];

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return <Badge className="text-[10px] bg-red-950/80 text-red-400 border border-red-800">CRITICAL</Badge>;
      case "WARNING":
        return <Badge className="text-[10px] bg-amber-950/80 text-amber-400 border border-amber-800">WARNING</Badge>;
      default:
        return <Badge className="text-[10px] bg-sky-950/80 text-sky-400 border border-sky-800">INFO</Badge>;
    }
  };

  // Determine active view mode
  const hasSelection = Boolean(
    selectedSubsystem || selectedInterface || selectedPowerDomain || selectedRequirement
  );

  return (
    <aside className="w-88 border-l border-zinc-800/80 bg-zinc-900/40 flex flex-col shrink-0 select-none overflow-hidden">
      {/* Top Header */}
      <div className="h-12 border-b border-zinc-800/80 px-4 flex items-center justify-between bg-zinc-900/60">
        <div className="flex items-center gap-2">
          {selectedSubsystem && (
            <>
              <Cpu className="w-4 h-4 text-sky-400" />
              <span className="text-xs font-semibold text-zinc-200">Subsystem Inspector</span>
            </>
          )}
          {selectedInterface && (
            <>
              <ArrowRight className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-semibold text-zinc-200">Interface Inspector</span>
            </>
          )}
          {selectedPowerDomain && (
            <>
              <Zap className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-semibold text-zinc-200">Power Rail Inspector</span>
            </>
          )}
          {selectedRequirement && (
            <>
              <FileCheck className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-semibold text-zinc-200">Requirement Inspector</span>
            </>
          )}
          {!hasSelection && (
            <>
              <ShieldAlert className="w-4 h-4 text-purple-400" />
              <span className="text-xs font-semibold text-zinc-200">System Verification</span>
            </>
          )}
        </div>

        {hasSelection && (
          <button
            onClick={onClearSelection}
            className="text-[11px] text-zinc-400 hover:text-zinc-200 underline"
          >
            Overview
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-800/80 bg-zinc-900/40 text-xs">
        <button
          onClick={() => setActiveTab("details")}
          className={`flex-1 py-2 text-center font-medium border-b-2 transition-colors ${
            activeTab === "details"
              ? "border-sky-500 text-sky-400 bg-zinc-800/40"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Properties
        </button>
        <button
          onClick={() => setActiveTab("findings")}
          className={`flex-1 py-2 text-center font-medium border-b-2 transition-colors flex items-center justify-center gap-1.5 ${
            activeTab === "findings"
              ? "border-sky-500 text-sky-400 bg-zinc-800/40"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <span>Findings</span>
          {findings.length > 0 && (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-red-950 text-red-300 border border-red-800/60 font-mono">
              {findings.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab("traceability")}
          className={`flex-1 py-2 text-center font-medium border-b-2 transition-colors ${
            activeTab === "traceability"
              ? "border-sky-500 text-sky-400 bg-zinc-800/40"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Traceability
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {/* TAB 1: PROPERTIES */}
        {activeTab === "details" && (
          <>
            {/* SUBSYSTEM SELECTED */}
            {selectedSubsystem && (
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <h2 className="text-sm font-bold text-zinc-100">{selectedSubsystem.name}</h2>
                    <Badge variant="outline" className="font-mono text-[10px] text-sky-400 border-sky-800">
                      Rev. {selectedSubsystem.revision}
                    </Badge>
                  </div>
                  <div className="text-[11px] text-zinc-400 font-mono">
                    Type: <span className="text-zinc-200 font-semibold">{selectedSubsystem.subsystem_type}</span>
                  </div>
                </div>

                {selectedSubsystem.description && (
                  <div className="p-2.5 rounded bg-zinc-950/60 border border-zinc-800/80 text-zinc-300">
                    {selectedSubsystem.description}
                  </div>
                )}

                {/* Circuit Link */}
                <div className="p-3 rounded bg-zinc-950/80 border border-zinc-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400 font-medium">Circuit Implementation</span>
                    {selectedSubsystem.circuit_id ? (
                      <Badge className="text-[10px] bg-purple-950 text-purple-300 border border-purple-800">
                        LINKED
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] text-zinc-500 border-zinc-700">
                        UNLINKED
                      </Badge>
                    )}
                  </div>
                  {selectedSubsystem.circuit_id && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="w-full text-xs border-purple-800/80 text-purple-300 bg-purple-950/30 hover:bg-purple-900/50 flex items-center justify-center gap-1.5"
                      onClick={() => onNavigateCircuit?.(selectedSubsystem.circuit_id!)}
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      <span>Open Circuit Schematic</span>
                    </Button>
                  )}
                </div>

                {/* Connected Interfaces */}
                <div className="space-y-2">
                  <h3 className="font-semibold text-zinc-300 text-[11px] uppercase tracking-wider">
                    Bound Interfaces
                  </h3>
                  {interfaces
                    .filter(
                      (i) =>
                        i.source_subsystem_id === selectedSubsystem.id ||
                        i.destination_subsystem_id === selectedSubsystem.id
                    )
                    .map((iface) => {
                      const isSource = iface.source_subsystem_id === selectedSubsystem.id;
                      return (
                        <div
                          key={iface.id}
                          onClick={() => onNavigateInterface?.(iface.id)}
                          className="p-2 rounded bg-zinc-950/50 border border-zinc-800/60 hover:border-zinc-700 cursor-pointer flex items-center justify-between"
                        >
                          <div className="flex items-center gap-1.5 truncate">
                            <span className="text-[10px] font-mono text-zinc-500">
                              {isSource ? "OUT" : "IN"}
                            </span>
                            <span className="text-zinc-200 truncate">{iface.name}</span>
                          </div>
                          <Badge variant="outline" className="text-[9px] font-mono border-zinc-700 text-zinc-400">
                            {iface.interface_type}
                          </Badge>
                        </div>
                      );
                    })}
                </div>

                {/* Power Domains */}
                <div className="space-y-2">
                  <h3 className="font-semibold text-zinc-300 text-[11px] uppercase tracking-wider">
                    Power Domains Provided
                  </h3>
                  {powerDomains
                    .filter((p) => p.source_subsystem_id === selectedSubsystem.id)
                    .map((domain) => (
                      <div
                        key={domain.id}
                        className="p-2 rounded bg-amber-950/20 border border-amber-900/40 flex items-center justify-between text-amber-200"
                      >
                        <div className="flex items-center gap-1.5">
                          <Zap className="w-3.5 h-3.5 text-amber-400" />
                          <span>{domain.name}</span>
                        </div>
                        <span className="font-mono font-bold">{domain.nominal_voltage}V</span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* INTERFACE SELECTED */}
            {selectedInterface && (
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <h2 className="text-sm font-bold text-zinc-100">{selectedInterface.name}</h2>
                    <Badge variant="outline" className="font-mono text-[10px] text-emerald-400 border-emerald-800">
                      {selectedInterface.interface_type}
                    </Badge>
                  </div>
                  <div className="text-[11px] text-zinc-500 font-mono">
                    ID: {selectedInterface.id}
                  </div>
                </div>

                {/* Source & Destination */}
                <div className="p-3 rounded bg-zinc-950/80 border border-zinc-800 space-y-2">
                  <div className="text-zinc-400 text-[11px] uppercase font-semibold">Connection Path</div>
                  <div className="flex items-center justify-between text-xs font-mono">
                    <div className="text-zinc-300">
                      <span className="text-zinc-500 block text-[10px]">SOURCE</span>
                      {subsystems.find((s) => s.id === selectedInterface.source_subsystem_id)?.name || "Unknown"}
                    </div>
                    <ArrowRight className="w-4 h-4 text-emerald-400" />
                    <div className="text-zinc-300 text-right">
                      <span className="text-zinc-500 block text-[10px]">DESTINATION</span>
                      {subsystems.find((s) => s.id === selectedInterface.destination_subsystem_id)?.name || "Unknown"}
                    </div>
                  </div>
                </div>

                {/* Contract Specification */}
                <div className="space-y-2">
                  <h3 className="font-semibold text-zinc-300 text-[11px] uppercase tracking-wider">
                    Interface Contract
                  </h3>
                  <div className="p-3 rounded bg-zinc-950/80 border border-zinc-800 space-y-2 font-mono text-[11px]">
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Protocol:</span>
                      <span className="text-zinc-200 font-semibold">{selectedInterface.contract?.protocol || "UNKNOWN"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Nominal Voltage:</span>
                      <span className="text-zinc-200">{selectedInterface.contract?.voltage_nominal !== undefined ? `${selectedInterface.contract.voltage_nominal}V` : "UNKNOWN"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Min / Max Voltage:</span>
                      <span className="text-zinc-200">
                        {selectedInterface.contract?.voltage_min !== undefined ? `${selectedInterface.contract.voltage_min}V` : "?"} /{" "}
                        {selectedInterface.contract?.voltage_max !== undefined ? `${selectedInterface.contract.voltage_max}V` : "?"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Max Current:</span>
                      <span className="text-zinc-200">{selectedInterface.contract?.max_current_a !== undefined ? `${selectedInterface.contract.max_current_a}A` : "UNKNOWN"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Baud / Clock:</span>
                      <span className="text-zinc-200">{selectedInterface.contract?.baud_rate || selectedInterface.contract?.clock_frequency_hz || "N/A"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Logic Level:</span>
                      <span className="text-zinc-200">{selectedInterface.contract?.logic_level || "UNKNOWN"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Galvanic Isolation:</span>
                      <span className={selectedInterface.contract?.galvanic_isolation ? "text-emerald-400 font-semibold" : "text-zinc-400"}>
                        {selectedInterface.contract?.galvanic_isolation ? "YES" : "NO"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* POWER DOMAIN SELECTED */}
            {selectedPowerDomain && (
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <h2 className="text-sm font-bold text-zinc-100">{selectedPowerDomain.name}</h2>
                    <Badge variant="outline" className="font-mono text-[10px] text-amber-400 border-amber-800">
                      {selectedPowerDomain.nominal_voltage}V RAIL
                    </Badge>
                  </div>
                  <div className="text-[11px] text-zinc-500 font-mono">
                    ID: {selectedPowerDomain.id}
                  </div>
                </div>

                <div className="p-3 rounded bg-zinc-950/80 border border-zinc-800 space-y-2 font-mono text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Nominal Voltage:</span>
                    <span className="text-amber-300 font-bold">{selectedPowerDomain.nominal_voltage}V</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Allowable Range:</span>
                    <span className="text-zinc-300">
                      {selectedPowerDomain.min_voltage ?? "?"}V – {selectedPowerDomain.max_voltage ?? "?"}V
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Current Capacity:</span>
                    <span className="text-emerald-400 font-bold">
                      {selectedPowerDomain.current_capacity_a !== undefined ? `${selectedPowerDomain.current_capacity_a} A` : "UNKNOWN"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Source Subsystem:</span>
                    <span className="text-zinc-300">
                      {subsystems.find((s) => s.id === selectedPowerDomain.source_subsystem_id)?.name || "External"}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* REQUIREMENT SELECTED */}
            {selectedRequirement && (
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <h2 className="text-sm font-bold text-cyan-300 font-mono">{selectedRequirement.code}</h2>
                    <Badge className="text-[10px]">{selectedRequirement.status}</Badge>
                  </div>
                  <div className="text-xs font-semibold text-zinc-100">
                    {selectedRequirement.title}
                  </div>
                </div>

                <div className="p-3 rounded bg-zinc-950/80 border border-zinc-800 text-zinc-300">
                  {selectedRequirement.description}
                </div>

                {selectedRequirement.source && (
                  <div className="p-2.5 rounded bg-zinc-950/50 border border-zinc-800 text-[11px]">
                    <span className="text-zinc-500 block uppercase font-mono text-[10px]">Evidence / Source</span>
                    <span className="text-zinc-300 font-mono">{selectedRequirement.source}</span>
                  </div>
                )}
              </div>
            )}

            {/* DEFAULT: NO SELECTION -> SYSTEM OVERVIEW */}
            {!hasSelection && (
              <div className="space-y-4">
                <div className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400 font-medium">System Metrics</span>
                    <Badge variant="outline" className="text-[10px] font-mono text-sky-400 border-sky-800">
                      Rev. {latestAnalysis?.system_revision ?? 1}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-center">
                    <div className="p-2 rounded bg-zinc-900 border border-zinc-800">
                      <div className="text-base font-bold text-zinc-100">{subsystems.length}</div>
                      <div className="text-[10px] text-zinc-500 uppercase">Subsystems</div>
                    </div>
                    <div className="p-2 rounded bg-zinc-900 border border-zinc-800">
                      <div className="text-base font-bold text-zinc-100">{interfaces.length}</div>
                      <div className="text-[10px] text-zinc-500 uppercase">Interfaces</div>
                    </div>
                    <div className="p-2 rounded bg-zinc-900 border border-zinc-800">
                      <div className="text-base font-bold text-zinc-100">{powerDomains.length}</div>
                      <div className="text-[10px] text-zinc-500 uppercase">Power Rails</div>
                    </div>
                    <div className="p-2 rounded bg-zinc-900 border border-zinc-800">
                      <div className="text-base font-bold text-zinc-100">{requirements.length}</div>
                      <div className="text-[10px] text-zinc-500 uppercase">Requirements</div>
                    </div>
                  </div>
                </div>

                <div className="p-3 rounded bg-zinc-950/60 border border-zinc-800/80 space-y-2">
                  <div className="flex items-center gap-1.5 text-zinc-400 font-semibold text-[11px] uppercase">
                    <Info className="w-3.5 h-3.5 text-sky-400" />
                    <span>Deterministic Architecture Rule</span>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-relaxed">
                    System verification operates under strict <span className="font-mono text-zinc-200">UNKNOWN != PASS</span> semantics. Missing voltage specifications, undefined baud rates, or unlinked circuits are never treated as validated.
                  </p>
                </div>
              </div>
            )}
          </>
        )}

        {/* TAB 2: FINDINGS */}
        {activeTab === "findings" && (
          <div className="space-y-3">
            {findings.length === 0 ? (
              <div className="text-center py-8 text-zinc-500 text-xs">
                No active findings. Run system analysis to evaluate compatibility.
              </div>
            ) : (
              findings.map((f) => (
                <div
                  key={f.id}
                  className="p-3 rounded-lg border bg-zinc-950/80 border-zinc-800 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] text-zinc-400">{f.rule_id}</span>
                    {getSeverityBadge(f.severity)}
                  </div>
                  <div className="font-semibold text-zinc-200 text-xs">{f.title}</div>
                  <p className="text-zinc-400 text-[11px] leading-relaxed">{f.description}</p>

                  {f.unknowns && f.unknowns.length > 0 && (
                    <div className="p-2 rounded bg-zinc-900/90 border border-zinc-800/80 text-[10px] font-mono text-amber-300">
                      <span className="text-zinc-500 block mb-0.5">Unknown Parameters:</span>
                      {f.unknowns.join(", ")}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB 3: TRACEABILITY */}
        {activeTab === "traceability" && (
          <div className="space-y-3">
            <div className="text-[11px] text-zinc-400 mb-2">
              Traceability links between system requirements and verified subsystems.
            </div>
            {requirements.map((req) => (
              <div key={req.id} className="p-3 rounded bg-zinc-950/80 border border-zinc-800 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-cyan-400 font-bold">{req.code}</span>
                  <Badge variant="outline" className="text-[10px] font-mono border-zinc-700 text-zinc-400">
                    {req.status}
                  </Badge>
                </div>
                <div className="text-zinc-200 font-medium text-xs">{req.title}</div>
                {req.source && (
                  <div className="text-[10px] font-mono text-zinc-500 truncate">
                    Ref: {req.source}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
};
