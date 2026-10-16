"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Target,
  Sliders,
  Play,
  Layers,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Plus,
  GitBranch,
  RefreshCw,
  Loader2,
  FileCheck,
  Cpu,
  Zap,
  ArrowRight,
  Scale,
  Sparkles,
  Lock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import {
  EngineeringSystem,
  EngineeringSubsystem,
  EngineeringSystemInterface,
  EngineeringPowerDomain,
} from "./types";
import {
  EngineeringSystemDesignObjective,
  EngineeringSystemDesignConstraint,
  EngineeringScenario,
  EngineeringScenarioResult,
  EngineeringSystemCandidate,
  EngineeringSystemProposal,
  ConstraintType,
  ConstraintStatus,
} from "./design_types";

interface SystemDesignTabProps {
  system: EngineeringSystem;
  subsystems: EngineeringSubsystem[];
  interfaces: EngineeringSystemInterface[];
  powerDomains: EngineeringPowerDomain[];
  onSystemUpdated: () => void;
}

export const SystemDesignTab: React.FC<SystemDesignTabProps> = ({
  system,
  subsystems,
  interfaces,
  powerDomains,
  onSystemUpdated,
}) => {
  const [subTab, setSubTab] = useState<"objectives" | "scenarios" | "candidates" | "proposals">("objectives");
  const [loading, setLoading] = useState(false);

  // Objectives & Constraints state
  const [objectives, setObjectives] = useState<EngineeringSystemDesignObjective[]>([]);
  const [selectedObjectiveId, setSelectedObjectiveId] = useState<string | null>(null);
  const [isCreatingObjective, setIsCreatingObjective] = useState(false);
  const [newObjTitle, setNewObjTitle] = useState("");
  const [newObjDesc, setNewObjDesc] = useState("");

  // Scenarios state
  const [scenarios, setScenarios] = useState<EngineeringScenario[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const [scenarioResults, setScenarioResults] = useState<Record<string, EngineeringScenarioResult>>({});
  const [isExecutingScenario, setIsExecutingScenario] = useState(false);
  const [isCreatingScenario, setIsCreatingScenario] = useState(false);
  const [newScenarioName, setNewScenarioName] = useState("");
  const [newScenarioType, setNewScenarioType] = useState<string>("OPERATING");

  // Candidates & Comparison state
  const [candidates, setCandidates] = useState<EngineeringSystemCandidate[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [isGeneratingCandidates, setIsGeneratingCandidates] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState("REGULATOR_REPLACEMENT");

  // Proposals state
  const [proposals, setProposals] = useState<EngineeringSystemProposal[]>([]);
  const [isSubmittingProposal, setIsSubmittingProposal] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Load design synthesis data
  const loadDesignData = useCallback(async () => {
    if (!system) return;
    setLoading(true);
    setActionError(null);
    try {
      // 1. Objectives
      const objRes = await apiClient.get<any>(`/systems/${system.id}/design/objectives`);
      const objs: EngineeringSystemDesignObjective[] = objRes.data?.data || [];
      setObjectives(objs);
      if (objs.length > 0 && !selectedObjectiveId) {
        setSelectedObjectiveId(objs[0]?.id ?? null);
      }

      // 2. Scenarios
      const scnRes = await apiClient.get<any>(`/systems/${system.id}/scenarios`);
      const scns: EngineeringScenario[] = scnRes.data?.data || [];
      setScenarios(scns);
      if (scns.length > 0 && !selectedScenarioId) {
        setSelectedScenarioId(scns[0]?.id ?? null);
      }

      // 3. Candidates for selected objective
      if (selectedObjectiveId) {
        const candRes = await apiClient.get<any>(`/design-objectives/${selectedObjectiveId}/candidates`);
        setCandidates(candRes.data?.data || []);
      }

      // 4. Proposals
      const propRes = await apiClient.get<any>(`/systems/${system.id}/design/proposals`);
      setProposals(propRes.data?.data || []);
    } catch (err: any) {
      console.error("Failed to load design synthesis data", err);
    } finally {
      setLoading(false);
    }
  }, [system, selectedObjectiveId]);

  useEffect(() => {
    loadDesignData();
  }, [loadDesignData]);

  // Handle Objective Creation
  const handleCreateObjective = async () => {
    if (!newObjTitle.trim() || !system) return;
    try {
      const res = await apiClient.post<any>(`/systems/${system.id}/design/objectives`, {
        title: newObjTitle.trim(),
        description: newObjDesc.trim(),
        target_subsystems: subsystems.map((s) => s.id),
        parameters: { target_revision: system.revision },
      });
      if (res.data?.data) {
        setObjectives((prev) => [res.data.data, ...prev]);
        setSelectedObjectiveId(res.data.data.id);
        setIsCreatingObjective(false);
        setNewObjTitle("");
        setNewObjDesc("");
      }
    } catch (e: any) {
      setActionError(e.response?.data?.detail || "Failed to create objective");
    }
  };

  // Handle Scenario Creation
  const handleCreateScenario = async () => {
    if (!newScenarioName.trim() || !system) return;
    try {
      const res = await apiClient.post<any>(`/systems/${system.id}/scenarios`, {
        name: newScenarioName.trim(),
        scenario_type: newScenarioType,
        preconditions: { system_active: true },
        is_active: true,
      });
      if (res.data?.data) {
        setScenarios((prev) => [res.data.data, ...prev]);
        setSelectedScenarioId(res.data.data.id);
        setIsCreatingScenario(false);
        setNewScenarioName("");
      }
    } catch (e: any) {
      setActionError(e.response?.data?.detail || "Failed to create scenario");
    }
  };

  // Handle Scenario Execution
  const handleExecuteScenario = async (scenarioId: string) => {
    setIsExecutingScenario(true);
    setActionError(null);
    try {
      const res = await apiClient.post<any>(`/scenarios/${scenarioId}/execute`);
      if (res.data?.data) {
        setScenarioResults((prev) => ({
          ...prev,
          [scenarioId]: res.data.data,
        }));
      }
    } catch (e: any) {
      setActionError(e.response?.data?.detail || "Failed to execute scenario");
    } finally {
      setIsExecutingScenario(false);
    }
  };

  // Handle Candidate Generation
  const handleGenerateCandidates = async () => {
    if (!selectedObjectiveId) return;
    setIsGeneratingCandidates(true);
    setActionError(null);
    try {
      const res = await apiClient.post<any>(`/design-objectives/${selectedObjectiveId}/candidates/generate`, {
        strategies: [selectedStrategy],
      });
      const generated = res.data?.data || [];
      setCandidates(generated);
      if (generated.length > 0) {
        setSelectedCandidateId(generated[0]?.id ?? null);
      }
      setSubTab("candidates");
    } catch (e: any) {
      setActionError(e.response?.data?.detail || "Failed to generate candidates");
    } finally {
      setIsGeneratingCandidates(false);
    }
  };

  // Handle Create Proposal From Candidate
  const handleCreateProposalFromCandidate = async (cand: EngineeringSystemCandidate) => {
    setIsSubmittingProposal(true);
    setActionError(null);
    try {
      const res = await apiClient.post<any>(`/systems/${system.id}/design/proposals`, {
        title: `Proposal: ${cand.title}`,
        base_revision: system.revision,
        candidate_id: cand.id,
        operations: cand.operations,
        generation_strategy: cand.strategy,
        rationale: cand.rationale,
      });
      if (res.data?.data) {
        setProposals((prev) => [res.data.data, ...prev]);
        setSubTab("proposals");
      }
    } catch (e: any) {
      setActionError(e.response?.data?.detail || "Failed to create proposal");
    } finally {
      setIsSubmittingProposal(false);
    }
  };

  // Handle Approve Proposal
  const handleApproveProposal = async (propId: string) => {
    setActionError(null);
    try {
      const res = await apiClient.post<any>(`/system-proposals/${propId}/approve`);
      if (res.data?.data) {
        setProposals((prev) =>
          prev.map((p) => (p.id === propId ? res.data.data : p))
        );
      }
    } catch (e: any) {
      setActionError(e.response?.data?.detail || "Approval failed");
    }
  };

  // Handle Atomic Apply Proposal
  const handleApplyProposal = async (propId: string) => {
    setActionError(null);
    try {
      const res = await apiClient.post<any>(`/system-proposals/${propId}/apply`);
      if (res.data?.data?.success) {
        await loadDesignData();
        onSystemUpdated();
      }
    } catch (e: any) {
      setActionError(e.response?.data?.detail || "Apply failed");
    }
  };

  const selectedObjective = objectives.find((o) => o.id === selectedObjectiveId);
  const selectedScenario = scenarios.find((s) => s.id === selectedScenarioId);
  const selectedCandidate = candidates.find((c) => c.id === selectedCandidateId);
  const activeScenarioResult = selectedScenarioId ? scenarioResults[selectedScenarioId] : null;

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-zinc-950 text-zinc-100">
      {/* Sub-Tabs Navigation */}
      <div className="h-10 border-b border-zinc-800/80 px-4 flex items-center justify-between bg-zinc-900/60 backdrop-blur shrink-0">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 mr-3 text-xs font-semibold text-sky-400">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Design Synthesis & Scenarios</span>
          </div>

          <div className="flex items-center bg-zinc-950 border border-zinc-800 rounded p-0.5">
            <button
              onClick={() => setSubTab("objectives")}
              className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
                subTab === "objectives"
                  ? "bg-zinc-800 text-sky-300 font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              1. Objectives & Constraints
            </button>
            <button
              onClick={() => setSubTab("scenarios")}
              className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
                subTab === "scenarios"
                  ? "bg-zinc-800 text-amber-300 font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              2. Scenario Intelligence
            </button>
            <button
              onClick={() => setSubTab("candidates")}
              className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
                subTab === "candidates"
                  ? "bg-zinc-800 text-purple-300 font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              3. Candidates & Comparison
            </button>
            <button
              onClick={() => setSubTab("proposals")}
              className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
                subTab === "proposals"
                  ? "bg-zinc-800 text-emerald-300 font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              4. Governance Proposals
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px] text-zinc-400 border-zinc-700 font-mono">
            System Rev. {system.revision}
          </Badge>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0 text-zinc-400 hover:text-zinc-200"
            onClick={loadDesignData}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* Global Error Banner */}
      {actionError && (
        <div className="bg-red-950/80 border-b border-red-800 px-4 py-2 flex items-center justify-between text-xs text-red-200">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{actionError}</span>
          </div>
          <button
            onClick={() => setActionError(null)}
            className="text-[11px] underline hover:text-white ml-3"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Tab 1: Objectives & Constraints */}
      {subTab === "objectives" && (
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Objectives List */}
          <div className="w-80 border-r border-zinc-800/80 bg-zinc-900/30 flex flex-col shrink-0">
            <div className="p-3 border-b border-zinc-800/80 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Design Objectives
              </span>
              <Button
                size="sm"
                variant="outline"
                className="h-6 text-[11px] border-zinc-700 bg-zinc-800/60 hover:bg-zinc-700"
                onClick={() => setIsCreatingObjective(!isCreatingObjective)}
              >
                <Plus className="w-3 h-3 mr-1" /> New
              </Button>
            </div>

            {isCreatingObjective && (
              <div className="p-3 border-b border-zinc-800 bg-zinc-900/90 flex flex-col gap-2">
                <input
                  type="text"
                  placeholder="Objective Title (e.g. Optimize Power)"
                  className="bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1 text-xs text-zinc-200 focus:outline-none focus:border-sky-500"
                  value={newObjTitle}
                  onChange={(e) => setNewObjTitle(e.target.value)}
                />
                <textarea
                  placeholder="Objective Description & Scope"
                  rows={2}
                  className="bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1 text-xs text-zinc-200 focus:outline-none focus:border-sky-500"
                  value={newObjDesc}
                  onChange={(e) => setNewObjDesc(e.target.value)}
                />
                <div className="flex items-center justify-end gap-2 mt-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 text-[11px]"
                    onClick={() => setIsCreatingObjective(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    className="h-6 text-[11px] bg-sky-600 hover:bg-sky-500 text-white"
                    onClick={handleCreateObjective}
                  >
                    Save Objective
                  </Button>
                </div>
              </div>
            )}

            <div className="flex-1 overflow-y-auto divide-y divide-zinc-800/50">
              {objectives.length === 0 ? (
                <div className="p-4 text-center text-xs text-zinc-500">
                  No design objectives defined yet. Click New to create one.
                </div>
              ) : (
                objectives.map((obj) => (
                  <div
                    key={obj.id}
                    onClick={() => setSelectedObjectiveId(obj.id)}
                    className={`p-3 cursor-pointer transition-colors ${
                      selectedObjectiveId === obj.id
                        ? "bg-sky-950/40 border-l-2 border-sky-400"
                        : "hover:bg-zinc-900/60"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-zinc-200 truncate">{obj.title}</span>
                      <Badge variant="outline" className="text-[9px] uppercase border-zinc-700">
                        {obj.status}
                      </Badge>
                    </div>
                    {obj.description && (
                      <p className="text-[11px] text-zinc-400 line-clamp-2 mt-1">{obj.description}</p>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Right: Objective Detail & Constraints */}
          <div className="flex-1 flex flex-col overflow-y-auto p-6 bg-zinc-950">
            {selectedObjective ? (
              <div className="max-w-4xl space-y-6">
                <div>
                  <div className="flex items-center justify-between">
                    <h2 className="text-base font-semibold text-zinc-100">{selectedObjective.title}</h2>
                    <Badge variant="outline" className="text-xs border-sky-800 text-sky-300">
                      Objective ID: {selectedObjective.id.slice(0, 8)}
                    </Badge>
                  </div>
                  {selectedObjective.description && (
                    <p className="text-xs text-zinc-400 mt-1">{selectedObjective.description}</p>
                  )}
                </div>

                {/* Synthesis Action Panel */}
                <div className="border border-sky-900/50 bg-sky-950/20 rounded-lg p-4 flex items-center justify-between">
                  <div className="space-y-1">
                    <span className="text-xs font-semibold text-sky-300 flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5" />
                      Deterministic Synthesis Engine
                    </span>
                    <p className="text-[11px] text-zinc-400">
                      Synthesize technically grounded candidates using registered strategies.
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <select
                      className="bg-zinc-900 border border-zinc-700 text-xs rounded px-2.5 py-1 text-zinc-200"
                      value={selectedStrategy}
                      onChange={(e) => setSelectedStrategy(e.target.value)}
                    >
                      <option value="REGULATOR_REPLACEMENT">Regulator Replacement</option>
                      <option value="SUBSYSTEM_ISOLATION">Subsystem Isolation</option>
                      <option value="PROTECTION_ADDITION">Protection Addition</option>
                      <option value="POWER_DOMAIN_RESTRUCTURE">Power Domain Restructure</option>
                    </select>

                    <Button
                      size="sm"
                      className="bg-sky-600 hover:bg-sky-500 text-white text-xs h-8 flex items-center gap-1.5"
                      onClick={handleGenerateCandidates}
                      disabled={isGeneratingCandidates}
                    >
                      {isGeneratingCandidates ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Play className="w-3.5 h-3.5" />
                      )}
                      <span>Synthesize Candidates</span>
                    </Button>
                  </div>
                </div>

                {/* Constraints Section */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
                      Objective Constraints (Hard & Soft)
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {/* Default Mock / Hardcoded for demo/workspace display */}
                    <div className="border border-zinc-800 bg-zinc-900/40 rounded p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-zinc-200">Max System Power</span>
                        <Badge variant="outline" className="text-[10px] text-red-400 border-red-800 bg-red-950/30">
                          HARD CONSTRAINT
                        </Badge>
                      </div>
                      <div className="text-xs text-zinc-400 font-mono">
                        Power dissipation &le; 15.0 W
                      </div>
                      <div className="text-[10px] text-zinc-500">
                        Must not be violated by any accepted proposal.
                      </div>
                    </div>

                    <div className="border border-zinc-800 bg-zinc-900/40 rounded p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-zinc-200">Regulator Efficiency</span>
                        <Badge variant="outline" className="text-[10px] text-blue-400 border-blue-800 bg-blue-950/30">
                          SOFT CONSTRAINT
                        </Badge>
                      </div>
                      <div className="text-xs text-zinc-400 font-mono">
                        Efficiency &ge; 85.0 %
                      </div>
                      <div className="text-[10px] text-zinc-500">
                        Optimized trade-off target across candidates.
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-zinc-500 text-xs">
                Select or create an objective to configure constraints and synthesize candidates.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Scenario Intelligence */}
      {subTab === "scenarios" && (
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Scenarios List */}
          <div className="w-80 border-r border-zinc-800/80 bg-zinc-900/30 flex flex-col shrink-0">
            <div className="p-3 border-b border-zinc-800/80 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Operating Scenarios
              </span>
              <Button
                size="sm"
                variant="outline"
                className="h-6 text-[11px] border-zinc-700 bg-zinc-800/60 hover:bg-zinc-700"
                onClick={() => setIsCreatingScenario(!isCreatingScenario)}
              >
                <Plus className="w-3 h-3 mr-1" /> New
              </Button>
            </div>

            {isCreatingScenario && (
              <div className="p-3 border-b border-zinc-800 bg-zinc-900/90 flex flex-col gap-2">
                <input
                  type="text"
                  placeholder="Scenario Name (e.g. Full Load Active)"
                  className="bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1 text-xs text-zinc-200 focus:outline-none focus:border-amber-500"
                  value={newScenarioName}
                  onChange={(e) => setNewScenarioName(e.target.value)}
                />
                <select
                  className="bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1 text-xs text-zinc-200"
                  value={newScenarioType}
                  onChange={(e) => setNewScenarioType(e.target.value)}
                >
                  <option value="OPERATING">Operating Condition</option>
                  <option value="FAILURE">Failure & Fault Injection</option>
                  <option value="STRESS">Thermal / Stress Load</option>
                  <option value="TRANSITION">Mode Transition</option>
                </select>
                <div className="flex items-center justify-end gap-2 mt-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 text-[11px]"
                    onClick={() => setIsCreatingScenario(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    className="h-6 text-[11px] bg-amber-600 hover:bg-amber-500 text-white"
                    onClick={handleCreateScenario}
                  >
                    Save Scenario
                  </Button>
                </div>
              </div>
            )}

            <div className="flex-1 overflow-y-auto divide-y divide-zinc-800/50">
              {scenarios.length === 0 ? (
                <div className="p-4 text-center text-xs text-zinc-500">
                  No scenarios defined. Click New to create a test scenario.
                </div>
              ) : (
                scenarios.map((sc) => (
                  <div
                    key={sc.id}
                    onClick={() => setSelectedScenarioId(sc.id)}
                    className={`p-3 cursor-pointer transition-colors ${
                      selectedScenarioId === sc.id
                        ? "bg-amber-950/40 border-l-2 border-amber-400"
                        : "hover:bg-zinc-900/60"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-zinc-200 truncate">{sc.name}</span>
                      <Badge variant="outline" className="text-[9px] uppercase border-zinc-700">
                        {sc.scenario_type}
                      </Badge>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Right: Scenario Execution & SHA-256 Snapshot Result */}
          <div className="flex-1 flex flex-col overflow-y-auto p-6 bg-zinc-950">
            {selectedScenario ? (
              <div className="max-w-4xl space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-zinc-100">{selectedScenario.name}</h2>
                    <p className="text-xs text-zinc-400 mt-1">
                      Type: {selectedScenario.scenario_type} &bull; System Rev: {system.revision}
                    </p>
                  </div>

                  <Button
                    size="sm"
                    className="bg-amber-600 hover:bg-amber-500 text-white text-xs h-8 flex items-center gap-1.5"
                    onClick={() => handleExecuteScenario(selectedScenario.id)}
                    disabled={isExecutingScenario}
                  >
                    {isExecutingScenario ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Play className="w-3.5 h-3.5" />
                    )}
                    <span>Execute & Snapshot</span>
                  </Button>
                </div>

                {/* Execution Results */}
                {activeScenarioResult ? (
                  <div className="space-y-4">
                    <div className="border border-zinc-800 bg-zinc-900/40 rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-zinc-200">Execution Status</span>
                        <Badge
                          variant="outline"
                          className={`text-xs font-mono ${
                            activeScenarioResult.execution_status === "SUCCESS"
                              ? "text-emerald-400 border-emerald-800 bg-emerald-950/30"
                              : activeScenarioResult.execution_status === "BLOCKED"
                              ? "text-red-400 border-red-800 bg-red-950/30"
                              : "text-amber-400 border-amber-800 bg-amber-950/30"
                          }`}
                        >
                          {activeScenarioResult.execution_status}
                        </Badge>
                      </div>

                      {/* Precondition Gate */}
                      <div className="border-t border-zinc-800/80 pt-2 text-xs space-y-1">
                        <div className="font-semibold text-zinc-400">Precondition Evaluation:</div>
                        <div className="flex items-center gap-2">
                          {activeScenarioResult.preconditions_evaluation.satisfied ? (
                            <span className="text-emerald-400 flex items-center gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5" /> Preconditions Satisfied
                            </span>
                          ) : (
                            <span className="text-red-400 flex items-center gap-1">
                              <XCircle className="w-3.5 h-3.5" /> Execution Blocked: Missing Preconditions
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Snapshot Info */}
                      {activeScenarioResult.snapshot_id && (
                        <div className="border-t border-zinc-800/80 pt-2 text-xs flex items-center justify-between font-mono text-zinc-400">
                          <span>Snapshot ID: {activeScenarioResult.snapshot_id.slice(0, 8)}</span>
                          <span className="text-[11px] text-zinc-500">Immutable SHA-256 Record</span>
                        </div>
                      )}
                    </div>

                    {/* Independent Consequences Deltas (Zero composite score) */}
                    <div className="border border-zinc-800 bg-zinc-900/30 rounded-lg p-4 space-y-3">
                      <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                        Consequences & Multidimensional Metrics
                      </span>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                        <div className="bg-zinc-950 border border-zinc-800 rounded p-2.5">
                          <div className="text-zinc-500 text-[10px] uppercase">Power Load</div>
                          <div className="text-zinc-200 font-mono font-semibold mt-1">
                            {activeScenarioResult.metrics?.total_power_load_w ?? "Unknown"} W
                          </div>
                        </div>

                        <div className="bg-zinc-950 border border-zinc-800 rounded p-2.5">
                          <div className="text-zinc-500 text-[10px] uppercase">Active Subsystems</div>
                          <div className="text-zinc-200 font-mono font-semibold mt-1">
                            {subsystems.length}
                          </div>
                        </div>

                        <div className="bg-zinc-950 border border-zinc-800 rounded p-2.5">
                          <div className="text-zinc-500 text-[10px] uppercase">Failure Blast Radius</div>
                          <div className="text-zinc-200 font-mono font-semibold mt-1">
                            {activeScenarioResult.consequences?.failure_evaluations?.length ?? 0} Subsystems
                          </div>
                        </div>

                        <div className="bg-zinc-950 border border-zinc-800 rounded p-2.5">
                          <div className="text-zinc-500 text-[10px] uppercase">Unknowns</div>
                          <div className="text-amber-400 font-mono font-semibold mt-1">
                            {activeScenarioResult.unknowns?.length ?? 0} Unresolved
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="border border-dashed border-zinc-800 rounded-lg p-8 text-center text-xs text-zinc-500">
                    Scenario has not been executed yet. Click "Execute & Snapshot" to run the deterministic simulation.
                  </div>
                )}
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-zinc-500 text-xs">
                Select or create a scenario to execute condition analysis.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Candidates & Comparison Matrix */}
      {subTab === "candidates" && (
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="p-4 border-b border-zinc-800/80 bg-zinc-900/40 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-zinc-200">
                Synthesized Architecture Alternatives
              </h2>
              <p className="text-[11px] text-zinc-400">
                Transparent comparison matrix against baseline. No composite score, no winner tags.
              </p>
            </div>

            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs border-zinc-700 bg-zinc-800 text-zinc-300"
              onClick={handleGenerateCandidates}
              disabled={isGeneratingCandidates || !selectedObjectiveId}
            >
              <Sparkles className="w-3.5 h-3.5 mr-1 text-sky-400" />
              Re-Synthesize Candidates
            </Button>
          </div>

          <div className="flex-1 overflow-auto p-6">
            {candidates.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-3">
                <Scale className="w-8 h-8 text-zinc-600" />
                <div className="text-xs text-zinc-400 max-w-md">
                  No architecture candidates generated for this objective yet. Go to "Objectives & Constraints" and click "Synthesize Candidates".
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Side-by-Side Comparison Table */}
                <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900/20">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-zinc-800 bg-zinc-900/80 font-semibold text-zinc-300">
                        <th className="p-3 w-48">Evaluation Metric</th>
                        <th className="p-3 border-l border-zinc-800 bg-zinc-950/60 text-zinc-400">
                          Baseline Architecture (Rev. {system.revision})
                        </th>
                        {candidates.map((cand, idx) => (
                          <th key={cand.id} className="p-3 border-l border-zinc-800 text-sky-300">
                            Candidate #{idx + 1}: {cand.title}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60 font-mono text-[11px]">
                      {/* Strategy */}
                      <tr>
                        <td className="p-3 font-sans font-medium text-zinc-400">Synthesis Strategy</td>
                        <td className="p-3 border-l border-zinc-800 text-zinc-400">BASELINE_DIRECT</td>
                        {candidates.map((cand) => (
                          <td key={cand.id} className="p-3 border-l border-zinc-800 text-zinc-200">
                            {cand.strategy}
                          </td>
                        ))}
                      </tr>

                      {/* Subsystems count */}
                      <tr>
                        <td className="p-3 font-sans font-medium text-zinc-400">Subsystem Count</td>
                        <td className="p-3 border-l border-zinc-800 text-zinc-300">{subsystems.length}</td>
                        {candidates.map((cand) => (
                          <td key={cand.id} className="p-3 border-l border-zinc-800 text-zinc-200">
                            {subsystems.length + cand.operations.filter((o) => o.op_type === "ADD_SUBSYSTEM").length - cand.operations.filter((o) => o.op_type === "REMOVE_SUBSYSTEM").length}
                          </td>
                        ))}
                      </tr>

                      {/* Interface Contracts */}
                      <tr>
                        <td className="p-3 font-sans font-medium text-zinc-400">Interface Contracts</td>
                        <td className="p-3 border-l border-zinc-800 text-zinc-300">
                          {interfaces.length} Interfaces Defined
                        </td>
                        {candidates.map((cand) => {
                          const ifaceEvals = cand.consequences?.simulation_result?.interface_evaluations || [];
                          const broken = ifaceEvals.filter((e) => e.status === "CONTRACT_VIOLATION").length;
                          return (
                            <td key={cand.id} className="p-3 border-l border-zinc-800">
                              {broken > 0 ? (
                                <span className="text-red-400 font-semibold">{broken} Violations</span>
                              ) : (
                                <span className="text-emerald-400 font-semibold">0 Violations</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>

                      {/* Verification Obligations */}
                      <tr>
                        <td className="p-3 font-sans font-medium text-zinc-400">Verification Obligations</td>
                        <td className="p-3 border-l border-zinc-800 text-zinc-300">Established</td>
                        {candidates.map((cand) => {
                          const vImpact = cand.consequences?.verification_impact || {};
                          const newReq = vImpact.new_verifications_required || [];
                          return (
                            <td key={cand.id} className="p-3 border-l border-zinc-800 text-amber-300">
                              +{newReq.length} New Verifications
                            </td>
                          );
                        })}
                      </tr>

                      {/* Unknowns / Unverified */}
                      <tr>
                        <td className="p-3 font-sans font-medium text-zinc-400">Unresolved Unknowns</td>
                        <td className="p-3 border-l border-zinc-800 text-zinc-400">0</td>
                        {candidates.map((cand) => {
                          const unk = cand.consequences?.simulation_result?.unknowns || [];
                          return (
                            <td key={cand.id} className="p-3 border-l border-zinc-800">
                              {unk.length > 0 ? (
                                <span className="text-amber-400">{unk.length} Unknowns</span>
                              ) : (
                                <span className="text-zinc-500">None</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>

                      {/* Action */}
                      <tr>
                        <td className="p-3 font-sans font-medium text-zinc-400">Action</td>
                        <td className="p-3 border-l border-zinc-800 text-zinc-500">Current Base</td>
                        {candidates.map((cand) => (
                          <td key={cand.id} className="p-3 border-l border-zinc-800">
                            <Button
                              size="sm"
                              className="h-6 text-[10px] bg-sky-600 hover:bg-sky-500 text-white"
                              onClick={() => handleCreateProposalFromCandidate(cand)}
                              disabled={isSubmittingProposal}
                            >
                              Create Proposal
                            </Button>
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Candidate Cards with Rationale & Trade-offs */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {candidates.map((cand, idx) => (
                    <div
                      key={cand.id}
                      className="border border-zinc-800 bg-zinc-900/40 rounded-lg p-4 space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-zinc-200">
                          #{idx + 1}: {cand.title}
                        </span>
                        <Badge variant="outline" className="text-[10px] border-zinc-700 font-mono">
                          {cand.strategy}
                        </Badge>
                      </div>

                      <p className="text-xs text-zinc-400">{cand.rationale}</p>

                      <div className="border-t border-zinc-800/80 pt-2 text-xs space-y-1">
                        <span className="text-[11px] font-semibold text-zinc-300">Proposed Operations:</span>
                        <ul className="list-disc list-inside text-zinc-400 text-[11px] space-y-0.5 font-mono">
                          {cand.operations.map((op, oIdx) => (
                            <li key={oIdx}>
                              {op.op_type} &mdash; {op.payload?.name || op.payload?.id || "parameter"}
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div className="flex items-center justify-end pt-2">
                        <Button
                          size="sm"
                          className="h-7 text-xs bg-sky-600 hover:bg-sky-500 text-white flex items-center gap-1.5"
                          onClick={() => handleCreateProposalFromCandidate(cand)}
                          disabled={isSubmittingProposal}
                        >
                          <FileCheck className="w-3.5 h-3.5" />
                          <span>Convert to Proposal</span>
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 4: Proposals & Governance */}
      {subTab === "proposals" && (
        <div className="flex-1 flex flex-col overflow-y-auto p-6 bg-zinc-950">
          <div className="max-w-4xl space-y-6">
            <div>
              <h2 className="text-sm font-semibold text-zinc-200">
                System Architecture Proposals & Controlled Governance
              </h2>
              <p className="text-xs text-zinc-400 mt-1">
                Every system proposal is cryptographically bound to base revision #{system.revision}. Stale proposals are rejected deterministically.
              </p>
            </div>

            {proposals.length === 0 ? (
              <div className="border border-dashed border-zinc-800 rounded-lg p-8 text-center text-xs text-zinc-500">
                No proposals exist for this system yet. Create one from the Candidates tab.
              </div>
            ) : (
              <div className="space-y-4">
                {proposals.map((prop) => {
                  const isStale = prop.base_revision !== system.revision || prop.status === "STALE";

                  return (
                    <div
                      key={prop.id}
                      className={`border rounded-lg p-5 space-y-3 ${
                        isStale
                          ? "border-amber-900/60 bg-amber-950/20"
                          : prop.status === "APPLIED"
                          ? "border-emerald-900/60 bg-emerald-950/20"
                          : "border-zinc-800 bg-zinc-900/40"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-zinc-100">{prop.title}</span>
                          <Badge
                            variant="outline"
                            className={`text-[10px] font-mono ${
                              prop.status === "APPLIED"
                                ? "text-emerald-400 border-emerald-800 bg-emerald-950/40"
                                : prop.status === "APPROVED"
                                ? "text-sky-400 border-sky-800 bg-sky-950/40"
                                : prop.status === "STALE" || isStale
                                ? "text-amber-400 border-amber-800 bg-amber-950/40"
                                : "text-zinc-400 border-zinc-700 bg-zinc-900"
                            }`}
                          >
                            {isStale && prop.status !== "APPLIED" ? "STALE" : prop.status}
                          </Badge>
                        </div>

                        <div className="text-xs font-mono text-zinc-400 flex items-center gap-1.5">
                          <GitBranch className="w-3.5 h-3.5" />
                          Base Rev: {prop.base_revision} (Current: {system.revision})
                        </div>
                      </div>

                      {prop.rationale && (
                        <p className="text-xs text-zinc-400">{prop.rationale}</p>
                      )}

                      {/* Operations list */}
                      <div className="bg-zinc-950/80 border border-zinc-800/80 rounded p-2.5 font-mono text-[11px] text-zinc-300 space-y-1">
                        <span className="text-[10px] uppercase text-zinc-500 font-sans font-semibold">
                          Operations:
                        </span>
                        {prop.operations.map((op, idx) => (
                          <div key={idx} className="flex items-center gap-2">
                            <ArrowRight className="w-3 h-3 text-sky-400 shrink-0" />
                            <span>
                              {op.op_type}: {op.payload?.name || op.payload?.id || JSON.stringify(op.payload)}
                            </span>
                          </div>
                        ))}
                      </div>

                      {/* Actions & Stale Protection */}
                      <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60">
                        {isStale && prop.status !== "APPLIED" ? (
                          <div className="text-xs text-amber-400 flex items-center gap-1.5">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            <span>System revision has advanced. This proposal is stale and cannot be applied.</span>
                          </div>
                        ) : (
                          <div className="text-xs text-zinc-500">
                            {prop.status === "APPLIED"
                              ? `Applied atomically at ${prop.applied_at?.slice(0, 19)}`
                              : "Human approval required prior to atomic application."}
                          </div>
                        )}

                        <div className="flex items-center gap-2">
                          {prop.status === "DRAFT" && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 text-xs border-sky-800 text-sky-300 bg-sky-950/40 hover:bg-sky-900/60"
                              onClick={() => handleApproveProposal(prop.id)}
                            >
                              Approve Proposal
                            </Button>
                          )}

                          {prop.status === "APPROVED" && (
                            <Button
                              size="sm"
                              className="h-7 text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-medium flex items-center gap-1.5"
                              onClick={() => handleApplyProposal(prop.id)}
                              disabled={isStale}
                            >
                              <Lock className="w-3.5 h-3.5" />
                              <span>Apply to System</span>
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
