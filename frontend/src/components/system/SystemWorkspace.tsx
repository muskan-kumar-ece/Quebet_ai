"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Layers,
  Cpu,
  Zap,
  Activity,
  ShieldAlert,
  Loader2,
  RefreshCw,
  Camera,
  AlertTriangle,
  CheckCircle2,
  Sliders,
  FileCheck,
  Plus,
  GitBranch,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import {
  EngineeringSystem,
  EngineeringSubsystem,
  EngineeringSystemInterface,
  EngineeringPowerDomain,
  EngineeringSystemDependency,
  EngineeringOperatingMode,
  EngineeringSystemRequirement,
  EngineeringSystemAnalysis,
  SystemDetailResponse,
} from "./types";
import { SystemCanvas } from "./SystemCanvas";
import { PowerTreeView } from "./PowerTreeView";
import { SystemTree } from "./SystemTree";
import { SystemInspector } from "./SystemInspector";
import { FailurePropagationModal } from "./FailurePropagationModal";
import { SystemDesignTab } from "./SystemDesignTab";
import { SystemDecisionCenterTab } from "./SystemDecisionCenterTab";
import { CognitiveWorkspace } from "../cognitive/CognitiveWorkspace";

interface SystemWorkspaceProps {
  projectId: string;
  projectName?: string;
  onNavigateCircuit?: (circuitId: string) => void;
}

export const SystemWorkspace: React.FC<SystemWorkspaceProps> = ({
  projectId,
  projectName = "System Architecture",
  onNavigateCircuit,
}) => {
  const [loading, setLoading] = useState(true);
  const [system, setSystem] = useState<EngineeringSystem | null>(null);
  const [subsystems, setSubsystems] = useState<EngineeringSubsystem[]>([]);
  const [interfaces, setInterfaces] = useState<EngineeringSystemInterface[]>([]);
  const [powerDomains, setPowerDomains] = useState<EngineeringPowerDomain[]>([]);
  const [dependencies, setDependencies] = useState<EngineeringSystemDependency[]>([]);
  const [operatingModes, setOperatingModes] = useState<EngineeringOperatingMode[]>([]);
  const [requirements, setRequirements] = useState<EngineeringSystemRequirement[]>([]);
  const [latestAnalysis, setLatestAnalysis] = useState<EngineeringSystemAnalysis | null>(null);

  // Selection states
  const [selectedSubsystemId, setSelectedSubsystemId] = useState<string | null>(null);
  const [selectedInterfaceId, setSelectedInterfaceId] = useState<string | null>(null);
  const [selectedPowerDomainId, setSelectedPowerDomainId] = useState<string | null>(null);
  const [selectedRequirementId, setSelectedRequirementId] = useState<string | null>(null);

  // View modes
  const [activeCenterView, setActiveCenterView] = useState<"architecture" | "power" | "design" | "decisions" | "cognitive">("architecture");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isCreatingSnapshot, setIsCreatingSnapshot] = useState(false);
  const [isFailureModalOpen, setIsFailureModalOpen] = useState(false);

  // Fetch or initialize system
  const loadSystem = useCallback(async () => {
    setLoading(true);
    try {
      // 1. Check if an EngineeringSystem exists for this project
      const listRes = await apiClient.get(`/systems?project_id=${projectId}`);
      let currentSystem: EngineeringSystem | null = null;
      if (listRes.data?.data && listRes.data.data.length > 0) {
        currentSystem = listRes.data.data[0];
      } else {
        // Create initial default system for project
        const createRes = await apiClient.post("/systems", {
          project_id: projectId,
          name: `${projectName} Architecture`,
          description: "System-level architecture and subsystem decomposition",
        });
        currentSystem = createRes.data?.data || null;
      }

      if (currentSystem) {
        // Fetch detailed system graph
        const detailRes = await apiClient.get<any>(`/systems/${currentSystem.id}`);
        const data = (detailRes.data?.data || detailRes.data) as SystemDetailResponse;
        if (data) {
          setSystem({
            id: data.id,
            project_id: data.project_id,
            name: data.name,
            description: data.description,
            revision: data.revision,
            status: data.status,
            created_by: data.created_by,
            created_at: data.created_at,
            updated_at: data.updated_at,
          });
          setSubsystems(data.subsystems || []);
          setInterfaces(data.interfaces || []);
          setPowerDomains(data.power_domains || []);
          setDependencies(data.dependencies || []);
          setOperatingModes(data.operating_modes || []);
          setRequirements(data.requirements || []);
          setLatestAnalysis(data.latest_analysis || null);
        }
      }
    } catch (err) {
      console.error("Failed to load system architecture:", err);
    } finally {
      setLoading(false);
    }
  }, [projectId, projectName]);

  useEffect(() => {
    loadSystem();
  }, [loadSystem]);

  const handleRunAnalysis = async () => {
    if (!system) return;
    setIsAnalyzing(true);
    try {
      const res = await apiClient.post(`/systems/${system.id}/analyze`);
      if (res.data?.data) {
        setLatestAnalysis(res.data.data);
      }
    } catch (e) {
      console.error("System analysis failed", e);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleCreateSnapshot = async () => {
    if (!system) return;
    setIsCreatingSnapshot(true);
    try {
      await apiClient.post(`/systems/${system.id}/snapshots`);
      await loadSystem();
    } catch (e) {
      console.error("Failed to create snapshot", e);
    } finally {
      setIsCreatingSnapshot(false);
    }
  };

  // Find currently selected objects
  const selectedSubsystem = subsystems.find((s) => s.id === selectedSubsystemId) || null;
  const selectedInterface = interfaces.find((i) => i.id === selectedInterfaceId) || null;
  const selectedPowerDomain = powerDomains.find((p) => p.id === selectedPowerDomainId) || null;
  const selectedRequirement = requirements.find((r) => r.id === selectedRequirementId) || null;

  const clearSelection = () => {
    setSelectedSubsystemId(null);
    setSelectedInterfaceId(null);
    setSelectedPowerDomainId(null);
    setSelectedRequirementId(null);
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-zinc-950 text-zinc-400">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-sky-400" />
          <span className="text-xs font-mono">Loading System Architecture...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-zinc-950 text-zinc-100">
      {/* System Sub-Header Controls */}
      <div className="h-12 border-b border-zinc-800/80 px-4 flex items-center justify-between bg-zinc-900/40 backdrop-blur shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-sky-400" />
            <span className="text-xs font-semibold text-zinc-200">{system?.name || "System"}</span>
          </div>

          <Badge variant="outline" className="text-[10px] text-sky-400 border-sky-800 font-mono flex items-center gap-1">
            <GitBranch className="w-3 h-3" />
            Rev. {system?.revision ?? 1}
          </Badge>

          <Badge
            variant="outline"
            className={`text-[10px] font-mono ${
              system?.status === "VERIFIED"
                ? "text-emerald-400 border-emerald-800 bg-emerald-950/40"
                : system?.status === "STALE"
                ? "text-amber-400 border-amber-800 bg-amber-950/40"
                : "text-zinc-400 border-zinc-700 bg-zinc-900"
            }`}
          >
            {system?.status || "ACTIVE"}
          </Badge>

          {/* View mode toggle */}
          <div className="flex items-center bg-zinc-900 border border-zinc-800 rounded p-0.5 ml-2">
            <button
              onClick={() => setActiveCenterView("architecture")}
              className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
                activeCenterView === "architecture"
                  ? "bg-zinc-800 text-sky-300 font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Architecture Diagram
            </button>
            <button
              onClick={() => setActiveCenterView("power")}
              className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
                activeCenterView === "power"
                  ? "bg-zinc-800 text-amber-300 font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Power Tree
            </button>
            <button
              onClick={() => setActiveCenterView("design")}
              className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
                activeCenterView === "design"
                  ? "bg-zinc-800 text-purple-300 font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Design Synthesis
            </button>
            <button
              onClick={() => setActiveCenterView("decisions")}
              className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
                activeCenterView === "decisions"
                  ? "bg-zinc-800 text-emerald-300 font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Decision Center
            </button>
            <button
              onClick={() => setActiveCenterView("cognitive")}
              className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
                activeCenterView === "cognitive"
                  ? "bg-zinc-800 text-sky-400 font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Cognitive Planner
            </button>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {/* Failure Simulation */}
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs border-red-800/80 bg-red-950/30 text-red-300 hover:bg-red-900/50 flex items-center gap-1.5"
            onClick={() => setIsFailureModalOpen(true)}
          >
            <ShieldAlert className="w-3.5 h-3.5 text-red-400" />
            <span>Simulate Failure</span>
          </Button>

          {/* Snapshot */}
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs border-zinc-700 bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 flex items-center gap-1.5"
            onClick={handleCreateSnapshot}
            disabled={isCreatingSnapshot}
          >
            {isCreatingSnapshot ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Camera className="w-3.5 h-3.5 text-zinc-400" />
            )}
            <span>Snapshot</span>
          </Button>

          {/* Analyze System */}
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs border-emerald-700/80 bg-emerald-950/40 hover:bg-emerald-900/60 text-emerald-300 flex items-center gap-1.5"
            onClick={handleRunAnalysis}
            disabled={isAnalyzing}
          >
            {isAnalyzing ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
            )}
            <span>Analyze System</span>
          </Button>
        </div>
      </div>

      {/* STALE ANALYSIS NOTIFICATION BANNER */}
      {latestAnalysis?.is_stale && (
        <div className="bg-amber-950/80 border-b border-amber-800/80 px-4 py-1.5 flex items-center justify-between text-xs text-amber-200 shrink-0">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              <strong>Stale Analysis:</strong> Architecture revisions have advanced since last evaluation. Re-run analysis to verify interface compatibility.
            </span>
          </div>
          <button
            onClick={handleRunAnalysis}
            className="text-[11px] underline hover:text-white font-medium ml-4 shrink-0"
          >
            Run Now
          </button>
        </div>
      )}

      {/* 3-PANE SYSTEM WORKSPACE */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: System Tree Navigator */}
        <SystemTree
          subsystems={subsystems}
          interfaces={interfaces}
          powerDomains={powerDomains}
          operatingModes={operatingModes}
          requirements={requirements}
          selectedSubsystemId={selectedSubsystemId}
          selectedInterfaceId={selectedInterfaceId}
          selectedPowerDomainId={selectedPowerDomainId}
          selectedRequirementId={selectedRequirementId}
          onSelectSubsystem={(s) => {
            clearSelection();
            setSelectedSubsystemId(s.id);
          }}
          onSelectInterface={(i) => {
            clearSelection();
            setSelectedInterfaceId(i.id);
          }}
          onSelectPowerDomain={(p) => {
            clearSelection();
            setSelectedPowerDomainId(p.id);
          }}
          onSelectRequirement={(r) => {
            clearSelection();
            setSelectedRequirementId(r.id);
          }}
        />

        {/* Center: System Canvas, Power Tree, Design Synthesis, Decision Center, or Cognitive Planner */}
        {activeCenterView === "cognitive" ? (
          <main className="flex-1 bg-zinc-950 flex flex-col relative overflow-hidden">
            <CognitiveWorkspace
              projectId={projectId}
              systemId={system?.id}
              systemRevision={system?.revision || 1}
            />
          </main>
        ) : activeCenterView === "decisions" && system ? (
          <main className="flex-1 bg-zinc-950 flex flex-col relative overflow-hidden">
            <SystemDecisionCenterTab
              system={system}
              onSystemUpdated={loadSystem}
            />
          </main>
        ) : activeCenterView === "design" && system ? (
          <main className="flex-1 bg-zinc-950 flex flex-col relative overflow-hidden">
            <SystemDesignTab
              system={system}
              subsystems={subsystems}
              interfaces={interfaces}
              powerDomains={powerDomains}
              onSystemUpdated={loadSystem}
            />
          </main>
        ) : (
          <>
            <main className="flex-1 bg-zinc-950 flex flex-col relative overflow-hidden">
              {activeCenterView === "architecture" ? (
                <SystemCanvas
                  subsystems={subsystems}
                  interfaces={interfaces}
                  powerDomains={powerDomains}
                  dependencies={dependencies}
                  selectedSubsystemId={selectedSubsystemId}
                  selectedInterfaceId={selectedInterfaceId}
                  onSelectSubsystem={(id) => {
                    clearSelection();
                    setSelectedSubsystemId(id);
                  }}
                  onSelectInterface={(id) => {
                    clearSelection();
                    setSelectedInterfaceId(id);
                  }}
                  viewMode="architecture"
                />
              ) : (
                <PowerTreeView
                  powerDomains={powerDomains}
                  subsystems={subsystems}
                  onSelectSubsystem={(id) => {
                    clearSelection();
                    setSelectedSubsystemId(id);
                  }}
                />
              )}
            </main>

            {/* Right: System Inspector */}
            <SystemInspector
              subsystems={subsystems}
              interfaces={interfaces}
              powerDomains={powerDomains}
              dependencies={dependencies}
              requirements={requirements}
              latestAnalysis={latestAnalysis}
              selectedSubsystem={selectedSubsystem}
              selectedInterface={selectedInterface}
              selectedPowerDomain={selectedPowerDomain}
              selectedRequirement={selectedRequirement}
              onNavigateSubsystem={(id) => {
                clearSelection();
                setSelectedSubsystemId(id);
              }}
              onNavigateInterface={(id) => {
                clearSelection();
                setSelectedInterfaceId(id);
              }}
              onNavigateCircuit={onNavigateCircuit}
              onClearSelection={clearSelection}
            />
          </>
        )}
      </div>

      {/* Failure Propagation Simulation Modal */}
      {isFailureModalOpen && system && (
        <FailurePropagationModal
          systemId={system.id}
          subsystems={subsystems}
          interfaces={interfaces}
          onClose={() => setIsFailureModalOpen(false)}
        />
      )}
    </div>
  );
};
