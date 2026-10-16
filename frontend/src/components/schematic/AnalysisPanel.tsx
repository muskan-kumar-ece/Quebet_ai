"use client";

import React, { useState } from "react";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Cpu,
  FileQuestion,
  HelpCircle,
  Info,
  Loader2,
  RefreshCw,
  Sparkles,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  CalculationItem,
  CircuitAnalysis,
  EngineeringUnknown,
  ExplainResponse,
  FindingItem,
  SimulationJob,
} from "./types";

interface AnalysisPanelProps {
  analysis: CircuitAnalysis | null;
  isLoading: boolean;
  onReanalyze: () => void;
  onExplain: (findingIds?: string[]) => Promise<ExplainResponse | null>;
  onCreateProposalFromFinding?: (finding: FindingItem) => void;
  onExploreDesignFix?: (finding: FindingItem) => void;
  simulationJob?: SimulationJob | null;
  onRunSimulation?: () => void;
}

export function AnalysisPanel({
  analysis,
  isLoading,
  onReanalyze,
  onExplain,
  onCreateProposalFromFinding,
  onExploreDesignFix,
  simulationJob,
  onRunSimulation,
}: AnalysisPanelProps) {
  const [activeTab, setActiveTab] = useState<"findings" | "calculations" | "unknowns" | "simulation" | "explanation">("findings");
  const [isExplaining, setIsExplaining] = useState(false);
  const [explanationData, setExplanationData] = useState<ExplainResponse | null>(null);

  const handleRequestExplanation = async (findingIds?: string[]) => {
    setIsExplaining(true);
    setActiveTab("explanation");
    try {
      const res = await onExplain(findingIds);
      if (res) {
        setExplanationData(res);
      }
    } finally {
      setIsExplaining(false);
    }
  };

  if (isLoading && !analysis) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center text-zinc-400">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-500 mb-3" />
        <p className="text-sm font-medium text-zinc-300">Evaluating circuit physics & rule engine...</p>
        <p className="text-xs text-zinc-500 mt-1">Executing Ohm's law, voltage dividers, and thermal dissipation models.</p>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center text-zinc-400">
        <Activity className="w-10 h-10 text-zinc-600 mb-3" />
        <h4 className="text-sm font-semibold text-zinc-200">No Analysis Available</h4>
        <p className="text-xs text-zinc-500 mt-1 max-w-xs">
          Run deterministic engineering analysis to verify electrical operating points, component ratings, and topology rules.
        </p>
        <Button
          onClick={onReanalyze}
          size="sm"
          className="mt-4 bg-emerald-600 hover:bg-emerald-500 text-white gap-2 text-xs"
        >
          <Zap className="w-3.5 h-3.5" />
          Run Engineering Analysis
        </Button>
      </div>
    );
  }

  const { status, confidence, execution_time_ms, findings, calculations, unknowns, graph_summary } = analysis;

  const statusColors = {
    COMPLETE: "bg-emerald-950/80 text-emerald-400 border-emerald-800/80",
    PARTIAL: "bg-amber-950/80 text-amber-400 border-amber-800/80",
    BLOCKED: "bg-red-950/80 text-red-400 border-red-800/80",
    INVALID: "bg-rose-950/80 text-rose-400 border-rose-800/80",
  }[status] || "bg-zinc-800 text-zinc-400 border-zinc-700";

  const criticalCount = findings.filter((f) => f.severity === "CRITICAL").length;
  const warningCount = findings.filter((f) => f.severity === "WARNING").length;

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-y-auto">
      {/* Top Header / Meta Bar */}
      <div className="p-4 border-b border-zinc-800/80 bg-zinc-900/60 sticky top-0 z-10 backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-400" />
            <h3 className="font-semibold text-sm tracking-wide text-zinc-100">Engineering Intelligence</h3>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onReanalyze}
            disabled={isLoading}
            className="h-7 text-xs border-zinc-700 bg-zinc-800/60 text-zinc-300 hover:bg-zinc-800 hover:text-white"
          >
            {isLoading ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" /> : <RefreshCw className="w-3 h-3 mr-1.5" />}
            Re-Analyze
          </Button>
        </div>

        {/* Badges Bar */}
        <div className="flex flex-wrap items-center gap-2 mt-3 text-xs">
          <Badge variant="outline" className={`px-2 py-0.5 font-mono text-[10px] tracking-wider ${statusColors}`}>
            {status}
          </Badge>
          <Badge variant="outline" className="px-2 py-0.5 font-mono text-[10px] border-zinc-700 text-zinc-400">
            CONFIDENCE: <span className="font-bold text-zinc-200 ml-1">{confidence}</span>
          </Badge>
          <span className="text-[11px] text-zinc-500 font-mono ml-auto">
            {execution_time_ms.toFixed(1)} ms
          </span>
        </div>

        {/* Power Domains Strip */}
        <div className="flex items-center gap-2 mt-2 pt-2 border-t border-zinc-800/50 text-[11px] text-zinc-400">
          <span className="text-zinc-500 font-medium">Power Rails:</span>
          {graph_summary?.power_nets?.length ? (
            graph_summary.power_nets.map((p) => (
              <span key={p} className="px-1.5 py-0.2 bg-amber-950/40 text-amber-300 border border-amber-800/40 rounded font-mono text-[10px]">
                {p}
              </span>
            ))
          ) : (
            <span className="text-zinc-600 text-[10px]">None detected</span>
          )}
          <span className="text-zinc-500 font-medium ml-2">Ground:</span>
          {graph_summary?.ground_nets?.length ? (
            graph_summary.ground_nets.map((g) => (
              <span key={g} className="px-1.5 py-0.2 bg-zinc-800 text-zinc-300 border border-zinc-700 rounded font-mono text-[10px]">
                {g}
              </span>
            ))
          ) : (
            <span className="text-zinc-600 text-[10px]">Floating</span>
          )}
        </div>
      </div>

      {/* Tabs Switcher */}
      <div className="flex border-b border-zinc-800 bg-zinc-900/30 text-xs px-2">
        <button
          onClick={() => setActiveTab("findings")}
          className={`flex items-center gap-1.5 py-2.5 px-3 border-b-2 font-medium transition-colors ${
            activeTab === "findings"
              ? "border-emerald-500 text-emerald-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          Findings ({findings.length})
          {criticalCount > 0 && (
            <span className="ml-1 px-1.5 py-0.2 bg-red-900/60 text-red-300 rounded-full text-[10px] font-bold">
              {criticalCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("calculations")}
          className={`flex items-center gap-1.5 py-2.5 px-3 border-b-2 font-medium transition-colors ${
            activeTab === "calculations"
              ? "border-emerald-500 text-emerald-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Zap className="w-3.5 h-3.5" />
          Calculations ({calculations.length})
        </button>

        <button
          onClick={() => setActiveTab("unknowns")}
          className={`flex items-center gap-1.5 py-2.5 px-3 border-b-2 font-medium transition-colors ${
            activeTab === "unknowns"
              ? "border-emerald-500 text-emerald-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <FileQuestion className="w-3.5 h-3.5" />
          Unknowns ({unknowns.length})
        </button>

        <button
          onClick={() => setActiveTab("simulation")}
          className={`flex items-center gap-1.5 py-2.5 px-3 border-b-2 font-medium transition-colors ${
            activeTab === "simulation"
              ? "border-cyan-500 text-cyan-400"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          SPICE Sim {simulationJob ? `(${simulationJob.status})` : ""}
        </button>

        <button
          onClick={() => setActiveTab("explanation")}
          className={`flex items-center gap-1.5 py-2.5 px-3 border-b-2 font-medium transition-colors ml-auto ${
            activeTab === "explanation"
              ? "border-indigo-500 text-indigo-400"
              : "border-transparent text-indigo-400/80 hover:text-indigo-300"
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          AI Synthesis
        </button>
      </div>

      {/* Main Tab Content */}
      <div className="p-4 space-y-3">
        {/* TAB 1: FINDINGS */}
        {activeTab === "findings" && (
          <div className="space-y-3">
            {findings.length === 0 ? (
              <div className="p-6 text-center border border-zinc-800/80 rounded-lg bg-zinc-900/20">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                <p className="text-sm font-medium text-zinc-200">No Rule Violations Detected</p>
                <p className="text-xs text-zinc-500 mt-1">Circuit complies with electrical rating limits and connectivity checks.</p>
              </div>
            ) : (
              findings.map((f) => {
                const isCritical = f.severity === "CRITICAL";
                return (
                  <Card
                    key={f.id}
                    className={`border ${
                      isCritical
                        ? "border-red-900/60 bg-red-950/20"
                        : "border-amber-900/50 bg-amber-950/15"
                    }`}
                  >
                    <CardHeader className="p-3 pb-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`font-mono text-[10px] font-bold px-1.5 py-0.5 rounded ${
                              isCritical ? "bg-red-900/80 text-red-200" : "bg-amber-900/80 text-amber-200"
                            }`}
                          >
                            {f.rule_id}
                          </span>
                          <CardTitle className="text-xs font-semibold text-zinc-200">{f.title}</CardTitle>
                        </div>
                        <div className="flex items-center gap-1.5">
                          {f.verification_status && (
                            <Badge
                              variant="outline"
                              className="text-[9px] px-1.5 py-0 font-mono font-medium border-cyan-800/80 text-cyan-400 bg-cyan-950/30"
                            >
                              {f.verification_status}
                            </Badge>
                          )}
                          <Badge
                            variant="outline"
                            className={`text-[9px] px-1.5 py-0 font-bold uppercase ${
                              isCritical ? "border-red-800 text-red-400" : "border-amber-800 text-amber-400"
                            }`}
                          >
                            {f.severity}
                          </Badge>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="p-3 pt-1 space-y-2">
                      <p className="text-xs text-zinc-300 leading-relaxed">{f.description}</p>
                      {(f.actual_value !== undefined && f.actual_value !== null && f.limit_value !== undefined && f.limit_value !== null) && (
                        <div className="bg-zinc-900/90 border border-zinc-800/80 px-2.5 py-1.5 rounded flex items-center justify-between text-[11px] font-mono">
                          <span className="text-zinc-400">
                            Actual: <strong className="text-amber-300">{typeof f.actual_value === "number" ? f.actual_value.toFixed(2) : f.actual_value} {f.unit || ""}</strong>
                          </span>
                          <span className="text-zinc-400">
                            Limit: <strong className="text-zinc-200">{typeof f.limit_value === "number" ? f.limit_value.toFixed(2) : f.limit_value} {f.unit || ""}</strong>
                          </span>
                        </div>
                      )}
                      {f.recommended_action && (
                        <div className="bg-zinc-900/80 border border-zinc-800 p-2 rounded text-[11px] text-zinc-300">
                          <span className="text-emerald-400 font-semibold">Recommended Fix: </span>
                          {f.recommended_action}
                        </div>
                      )}
                      <div className="flex items-center justify-between pt-1 text-[11px]">
                        <span className="text-zinc-500 font-mono text-[10px]">{f.provenance}</span>
                        <div className="flex items-center gap-1">
                          {onExploreDesignFix && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => onExploreDesignFix(f)}
                              className="h-6 text-[11px] text-amber-400 hover:text-amber-300 hover:bg-amber-950/50 px-2"
                            >
                              Explore Fixes <ChevronRight className="w-3 h-3 ml-0.5" />
                            </Button>
                          )}
                          {onCreateProposalFromFinding && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => onCreateProposalFromFinding(f)}
                              className="h-6 text-[11px] text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/50 px-2"
                            >
                              Create Proposal <ChevronRight className="w-3 h-3 ml-0.5" />
                            </Button>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })
            )}
          </div>
        )}

        {/* TAB 2: CALCULATIONS */}
        {activeTab === "calculations" && (
          <div className="space-y-3">
            {calculations.length === 0 ? (
              <div className="p-6 text-center border border-zinc-800/80 rounded-lg text-zinc-500 text-xs">
                No electrical calculations could be derived from current topology.
              </div>
            ) : (
              calculations.map((c) => (
                <Card key={c.id} className="border border-zinc-800 bg-zinc-900/40">
                  <CardHeader className="p-3 pb-2 flex flex-row items-center justify-between">
                    <div>
                      <span className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider">{c.category}</span>
                      <h4 className="text-xs font-semibold text-zinc-200">{c.name}</h4>
                    </div>
                    <span className="text-[10px] font-mono bg-zinc-800 text-zinc-300 px-1.5 py-0.5 rounded border border-zinc-700">
                      {c.formula}
                    </span>
                  </CardHeader>
                  <CardContent className="p-3 pt-0 space-y-2">
                    {/* Inputs and Results Grid */}
                    <div className="grid grid-cols-2 gap-2 text-[11px] bg-zinc-950/60 p-2 rounded border border-zinc-800/60">
                      <div>
                        <span className="text-zinc-500 block text-[10px] font-medium uppercase mb-0.5">Inputs</span>
                        {Object.entries(c.inputs).map(([k, v]) => (
                          <div key={k} className="flex justify-between font-mono text-zinc-300">
                            <span className="text-zinc-500">{k}:</span>
                            <span>{String(v)}</span>
                          </div>
                        ))}
                      </div>
                      <div className="border-l border-zinc-800 pl-2">
                        <span className="text-zinc-500 block text-[10px] font-medium uppercase mb-0.5">Outputs</span>
                        {Object.entries(c.result).map(([k, v]) => (
                          <div key={k} className="flex justify-between font-mono text-emerald-400 font-medium">
                            <span className="text-zinc-400">{k}:</span>
                            <span>{String(v)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    {c.notes && <p className="text-[11px] text-zinc-400 italic">{c.notes}</p>}
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        )}

        {/* TAB 3: UNKNOWNS */}
        {activeTab === "unknowns" && (
          <div className="space-y-3">
            {unknowns.length === 0 ? (
              <div className="p-6 text-center border border-zinc-800/80 rounded-lg text-emerald-400 text-xs">
                All component parameters and boundaries are fully specified.
              </div>
            ) : (
              unknowns.map((u) => (
                <div key={u.id} className="p-3 rounded-lg border border-amber-900/40 bg-amber-950/10 text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-amber-300 uppercase text-[10px]">{u.field}</span>
                    <span className="text-zinc-500 text-[10px]">Uncertified</span>
                  </div>
                  <p className="text-zinc-300">{u.reason}</p>
                  <p className="text-zinc-500 text-[11px]">
                    <span className="text-zinc-400 font-medium">Impact:</span> {u.impact}
                  </p>
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB 4: SPICE SIMULATION */}
        {activeTab === "simulation" && (
          <div className="space-y-3">
            {/* Epistemic Invariant Alert */}
            <div className="p-3 rounded-lg border border-cyan-900/60 bg-cyan-950/20 text-xs space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-cyan-900/80 text-cyan-200 uppercase">
                  CALCULATED_RESULT
                </span>
                <span className="text-[10px] text-zinc-400 font-mono">
                  VERIFICATION: <span className="text-amber-400 font-bold">NOT_VERIFIED</span>
                </span>
              </div>
              <p className="text-[11px] text-zinc-300">
                SPICE simulation results are numerical calculations based on idealized mathematical models.
                They <span className="font-semibold text-zinc-200">do not</span> constitute physical hardware test or physical verification.
              </p>
            </div>

            {!simulationJob ? (
              <div className="p-6 text-center border border-zinc-800/80 rounded-lg bg-zinc-900/20 space-y-3">
                <Activity className="w-8 h-8 text-cyan-500 mx-auto" />
                <p className="text-sm font-medium text-zinc-200">No Simulation Run for this Revision</p>
                <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                  Execute deterministic SPICE simulation (MNA / ngspice) to compute exact DC operating points, node voltages, and branch currents.
                </p>
                {onRunSimulation && (
                  <Button
                    onClick={onRunSimulation}
                    size="sm"
                    className="bg-cyan-600 hover:bg-cyan-500 text-white gap-1.5 text-xs font-medium"
                  >
                    <Activity className="w-3.5 h-3.5" />
                    Run SPICE Simulation
                  </Button>
                )}
              </div>
            ) : (
              <div className="space-y-3 text-xs">
                {/* Simulator Metadata */}
                <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-900/40 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400 font-medium">Simulator Engine:</span>
                    <span className="font-mono text-zinc-200">{simulationJob.simulator} ({simulationJob.execution_mode})</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400 font-medium">Convergence:</span>
                    <Badge variant="outline" className={`font-mono text-[10px] ${
                      simulationJob.result?.convergence_status === "CONVERGED"
                        ? "border-emerald-800 text-emerald-400 bg-emerald-950/40"
                        : "border-red-800 text-red-400 bg-red-950/40"
                    }`}>
                      {simulationJob.result?.convergence_status || "UNKNOWN"}
                    </Badge>
                  </div>
                  {simulationJob.netlist_digest && (
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-400 font-medium">Netlist Digest:</span>
                      <span className="font-mono text-[10px] text-zinc-500">{simulationJob.netlist_digest.slice(0, 16)}...</span>
                    </div>
                  )}
                </div>

                {/* Node Voltages Table */}
                {simulationJob.result?.node_voltages && (
                  <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-900/40 space-y-2">
                    <h4 className="font-semibold text-zinc-200 text-xs">Node Voltages</h4>
                    <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
                      {Object.entries(simulationJob.result.node_voltages).map(([node, v]) => (
                        <div key={node} className="flex justify-between p-1.5 rounded bg-zinc-950/60 border border-zinc-800/60">
                          <span className="text-zinc-400">{node}:</span>
                          <span className="text-emerald-400 font-semibold">{v.toFixed(3)} V</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Discrepancies vs Analytical Calculations */}
                {simulationJob.result?.discrepancies && simulationJob.result.discrepancies.length > 0 && (
                  <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-900/40 space-y-2">
                    <h4 className="font-semibold text-zinc-200 text-xs">Analytical vs Simulation Comparison</h4>
                    <div className="space-y-1.5">
                      {simulationJob.result.discrepancies.map((disc, idx) => {
                        const isDiscrepancy = disc.flag === "ANALYSIS_SIMULATION_DISCREPANCY";
                        return (
                          <div key={idx} className={`p-2 rounded border text-[11px] ${
                            isDiscrepancy ? "border-amber-800/80 bg-amber-950/20" : "border-zinc-800 bg-zinc-950/40"
                          }`}>
                            <div className="flex justify-between items-center">
                              <span className="font-mono text-zinc-300">{disc.element_or_node} ({disc.parameter})</span>
                              <Badge variant="outline" className={`text-[9px] ${
                                isDiscrepancy ? "border-amber-700 text-amber-400" : "border-emerald-700 text-emerald-400"
                              }`}>
                                {disc.flag}
                              </Badge>
                            </div>
                            <div className="flex gap-3 text-zinc-400 mt-1 font-mono text-[10px]">
                              <span>Analytical: {disc.analytical_value}{disc.unit}</span>
                              <span>Simulated: {disc.simulation_value}{disc.unit}</span>
                              <span>Delta: {(disc.relative_delta * 100).toFixed(1)}%</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Constraint Evaluations */}
                {simulationJob.result?.constraint_evaluations && simulationJob.result.constraint_evaluations.length > 0 && (
                  <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-900/40 space-y-2">
                    <h4 className="font-semibold text-zinc-200 text-xs">Operating Limits & Constraints</h4>
                    <div className="space-y-1.5">
                      {simulationJob.result.constraint_evaluations.map((ce, idx) => (
                        <div key={idx} className={`p-2 rounded border text-[11px] ${
                          ce.status === "VIOLATED" ? "border-red-800/80 bg-red-950/20" : "border-zinc-800 bg-zinc-950/40"
                        }`}>
                          <div className="flex justify-between items-center">
                            <span className="font-mono text-zinc-300">{ce.constraint_id}</span>
                            <Badge variant="outline" className={`text-[9px] ${
                              ce.status === "VIOLATED" ? "border-red-700 text-red-400" : "border-emerald-700 text-emerald-400"
                            }`}>
                              {ce.status}
                            </Badge>
                          </div>
                          <div className="flex gap-3 text-zinc-400 mt-1 font-mono text-[10px]">
                            <span>Sim: {ce.simulated_value}{ce.unit}</span>
                            <span>Limit: {ce.limit_value}{ce.unit}</span>
                            {ce.margin !== null && ce.margin !== undefined && <span>Margin: {(ce.margin * 100).toFixed(1)}%</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 5: AI SYNTHESIS / EXPLANATION */}
        {activeTab === "explanation" && (
          <div className="space-y-4">
            <div className="p-3 rounded-lg border border-indigo-900/60 bg-indigo-950/20 text-xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-indigo-300 font-semibold">
                  <Sparkles className="w-4 h-4" />
                  Engineering Reasoning & Synthesis
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleRequestExplanation()}
                  disabled={isExplaining}
                  className="h-6 text-[10px] border-indigo-700 bg-indigo-900/40 text-indigo-200 hover:bg-indigo-800"
                >
                  {isExplaining ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <RefreshCw className="w-3 h-3 mr-1" />}
                  Synthesize
                </Button>
              </div>
              <p className="text-zinc-400 text-[11px]">
                Grounds all reasoning in deterministic physics equations without altering computed values.
              </p>
            </div>

            {isExplaining && (
              <div className="p-8 text-center text-zinc-400">
                <Loader2 className="w-6 h-6 animate-spin text-indigo-400 mx-auto mb-2" />
                <p className="text-xs">Analyzing physical mechanisms and engineering trade-offs...</p>
              </div>
            )}

            {!isExplaining && explanationData && (
              <div className="space-y-3 text-xs">
                {/* Physical Mechanisms */}
                <div className="border border-zinc-800 bg-zinc-900/40 rounded-lg p-3 space-y-2">
                  <h4 className="font-semibold text-zinc-200 text-xs flex items-center gap-1.5">
                    <Cpu className="w-3.5 h-3.5 text-emerald-400" />
                    Physical Mechanisms Identified
                  </h4>
                  <ul className="space-y-1.5 text-zinc-300">
                    {explanationData.identified_mechanisms.map((m, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-emerald-400 mt-0.5">•</span>
                        <span>{m}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Engineering Trade-offs */}
                <div className="border border-zinc-800 bg-zinc-900/40 rounded-lg p-3 space-y-2">
                  <h4 className="font-semibold text-zinc-200 text-xs flex items-center gap-1.5">
                    <AlertOctagon className="w-3.5 h-3.5 text-amber-400" />
                    Design Trade-Offs
                  </h4>
                  <ul className="space-y-1.5 text-zinc-300">
                    {explanationData.engineering_tradeoffs.map((t, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-amber-400 mt-0.5">•</span>
                        <span>{t}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Recommended Actions */}
                <div className="border border-zinc-800 bg-zinc-900/40 rounded-lg p-3 space-y-2">
                  <h4 className="font-semibold text-zinc-200 text-xs flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" />
                    Actionable Recommendations
                  </h4>
                  <ul className="space-y-1.5 text-zinc-300">
                    {explanationData.recommended_actions.map((a, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-indigo-400 mt-0.5">•</span>
                        <span>{a}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
