"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Layers,
  Cpu,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Activity,
  GitBranch,
  RefreshCw,
  Loader2,
  Info,
  Maximize2,
  Minimize2,
  FileCode,
  Sliders,
  Check,
  X,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { apiClient } from "@/lib/api";
import {
  EngineeringBoard,
  PCBAnalysisRecord,
  PCBFinding,
  PCBProposal,
  PCBConstraintEvaluation,
} from "./types";

interface PCBIntelligenceTabProps {
  circuitId: string | null;
}

export function PCBIntelligenceTab({ circuitId }: PCBIntelligenceTabProps) {
  const queryClient = useQueryClient();
  const [activeSubTab, setActiveSubTab] = useState<"drc" | "stackup" | "proposals">("drc");
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");
  const [selectedFinding, setSelectedFinding] = useState<PCBFinding | null>(null);

  // Fetch Board for this circuit
  const {
    data: board,
    isLoading: isBoardLoading,
    refetch: refetchBoard,
  } = useQuery<EngineeringBoard>({
    queryKey: ["engineering-board", circuitId],
    queryFn: async () => {
      if (!circuitId) throw new Error("No circuit ID");
      const res = await apiClient.get(`/pcb/boards/by-circuit/${circuitId}`);
      return res.data?.data;
    },
    enabled: !!circuitId,
  });

  // Fetch latest DRC analysis for this board
  const {
    data: analysis,
    isLoading: isAnalysisLoading,
    refetch: refetchAnalysis,
  } = useQuery<PCBAnalysisRecord>({
    queryKey: ["pcb-analysis", board?.id],
    queryFn: async () => {
      if (!board?.id) throw new Error("No board ID");
      const res = await apiClient.post(`/pcb/boards/${board.id}/analyze`);
      return res.data?.data;
    },
    enabled: !!board?.id,
  });

  // Run Analysis Mutation
  const analyzeMutation = useMutation({
    mutationFn: async () => {
      if (!board?.id) throw new Error("No board ID");
      const res = await apiClient.post(`/pcb/boards/${board.id}/analyze`);
      return res.data?.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["pcb-analysis", board?.id], data);
    },
  });

  // Fetch proposals
  const { data: proposals, refetch: refetchProposals } = useQuery<PCBProposal[]>({
    queryKey: ["pcb-proposals", board?.id],
    queryFn: async () => {
      if (!board?.id) return [];
      const res = await apiClient.get(`/pcb/boards/${board.id}/proposals`);
      return res.data?.data || [];
    },
    enabled: !!board?.id,
  });

  // Approve proposal mutation (Human gate)
  const approveMutation = useMutation({
    mutationFn: async (proposalId: string) => {
      const res = await apiClient.post(`/pcb/proposals/${proposalId}/approve`);
      return res.data?.data;
    },
    onSuccess: () => {
      refetchProposals();
      refetchBoard();
      refetchAnalysis();
    },
  });

  const findings = analysis?.findings || [];
  const filteredFindings = findings.filter((f) => {
    if (filterSeverity === "ALL") return true;
    return f.severity === filterSeverity;
  });

  const errorCount = findings.filter((f) => f.severity === "ERROR").length;
  const warningCount = findings.filter((f) => f.severity === "WARNING").length;
  const unknownCount = findings.filter((f) => f.status === "UNKNOWN").length;

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Epistemic Invariant Safety Banner */}
      <div className="bg-amber-950/40 border border-amber-900/60 rounded-md p-2.5 text-xs text-amber-300/90 flex items-start gap-2.5">
        <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <div className="space-y-0.5 leading-relaxed">
          <div className="font-semibold text-amber-200 uppercase tracking-wider text-[11px]">
            PCB Analytical Verification Boundary
          </div>
          <p className="text-[11px] text-amber-300/80">
            <span className="font-mono font-semibold">PCB_ANALYSIS ≠ PCB_FABRICATION ≠ PCB_INSPECTION ≠ HARDWARE_TEST</span>
            . Verification is bounded to physical and schematic model consistency. Incomplete parameters evaluate to{" "}
            <span className="font-mono font-semibold">UNKNOWN</span>, never assumed satisfied. Zero synthetic scoring.
          </p>
        </div>
      </div>

      {/* Board Metadata & Provenance Digest Header */}
      <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-sky-400" />
            <span className="text-xs font-semibold text-zinc-200">
              {board?.name || "Target PCB Board"}
            </span>
            <Badge variant="outline" className="text-[10px] text-zinc-400 border-zinc-700 font-mono">
              Rev {board?.revision ?? 1}
            </Badge>
            <Badge variant="outline" className="text-[10px] text-sky-400 border-sky-800 bg-sky-950/40 font-mono">
              {board?.width_mm ?? 100} × {board?.height_mm ?? 80} {board?.units ?? "MM"}
            </Badge>
            <Badge variant="outline" className="text-[10px] text-purple-400 border-purple-800 bg-purple-950/40 font-mono">
              {board?.layer_count ?? 2} Layers
            </Badge>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => analyzeMutation.mutate()}
            disabled={analyzeMutation.isPending || isBoardLoading}
            className="h-7 px-2.5 text-xs border-emerald-800/80 bg-emerald-950/40 hover:bg-emerald-900/60 text-emerald-300 flex items-center gap-1.5"
          >
            {analyzeMutation.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
            )}
            <span>Run DRC Analysis</span>
          </Button>
        </div>

        {analysis?.provenance_digest && (
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-zinc-500 bg-zinc-950/70 px-2 py-1 rounded border border-zinc-800/80">
            <FileCode className="w-3 h-3 text-zinc-400" />
            <span className="text-zinc-400">Snapshot Digest:</span>
            <span className="text-sky-300/80 truncate">{analysis.provenance_digest}</span>
          </div>
        )}
      </div>

      {/* Sub-Tabs: DRC Findings, Stackup, Proposals */}
      <div className="flex items-center border-b border-zinc-800 p-1 gap-1 bg-zinc-900/50 rounded-md">
        <button
          onClick={() => setActiveSubTab("drc")}
          className={`flex-1 py-1 text-xs font-medium rounded transition-colors flex items-center justify-center gap-1.5 ${
            activeSubTab === "drc"
              ? "bg-zinc-800 text-sky-400 font-semibold shadow-sm"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>DRC Rules ({findings.length})</span>
          {errorCount > 0 && (
            <span className="px-1.5 py-0.2 bg-red-950 text-red-300 rounded-full text-[9px] font-bold border border-red-800">
              {errorCount}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveSubTab("stackup")}
          className={`flex-1 py-1 text-xs font-medium rounded transition-colors flex items-center justify-center gap-1.5 ${
            activeSubTab === "stackup"
              ? "bg-zinc-800 text-purple-400 font-semibold shadow-sm"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Layer Stackup</span>
        </button>
        <button
          onClick={() => setActiveSubTab("proposals")}
          className={`flex-1 py-1 text-xs font-medium rounded transition-colors flex items-center justify-center gap-1.5 ${
            activeSubTab === "proposals"
              ? "bg-zinc-800 text-emerald-400 font-semibold shadow-sm"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <GitBranch className="w-3.5 h-3.5" />
          <span>Layout Proposals</span>
          {proposals && proposals.length > 0 && (
            <span className="px-1.5 py-0.2 bg-emerald-950 text-emerald-300 rounded-full text-[9px] font-bold border border-emerald-800">
              {proposals.length}
            </span>
          )}
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto space-y-3">
        {activeSubTab === "drc" && (
          <div className="space-y-3">
            {/* Filter Buttons */}
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-400 text-[11px] font-mono">
                Physical Clearance & Continuity Checks (PCB001–PCB016)
              </span>
              <div className="flex items-center gap-1">
                {(["ALL", "ERROR", "WARNING"] as const).map((sev) => (
                  <button
                    key={sev}
                    onClick={() => setFilterSeverity(sev)}
                    className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                      filterSeverity === sev
                        ? "bg-zinc-800 text-zinc-100 border border-zinc-700"
                        : "text-zinc-500 hover:text-zinc-300"
                    }`}
                  >
                    {sev}
                  </button>
                ))}
              </div>
            </div>

            {/* Findings List */}
            {isAnalysisLoading ? (
              <div className="flex items-center justify-center p-8 text-zinc-500 gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
                <span className="text-xs">Evaluating DRC rules...</span>
              </div>
            ) : filteredFindings.length === 0 ? (
              <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-6 text-center space-y-1.5">
                <CheckCircle2 className="w-6 h-6 text-emerald-400 mx-auto" />
                <div className="text-xs font-medium text-zinc-200">No DRC Violations Found</div>
                <div className="text-[11px] text-zinc-500">
                  All evaluated physical constraints and schematic consistencies are satisfied.
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredFindings.map((f, idx) => {
                  const isErr = f.severity === "ERROR";
                  const isWarn = f.severity === "WARNING";
                  const isUnknown = f.status === "UNKNOWN";

                  return (
                    <div
                      key={idx}
                      onClick={() => setSelectedFinding(f)}
                      className={`p-3 rounded-lg border transition-colors cursor-pointer ${
                        selectedFinding === f
                          ? "bg-zinc-800/80 border-sky-600"
                          : "bg-zinc-900/60 border-zinc-800 hover:border-zinc-700"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          {isErr ? (
                            <XCircle className="w-4 h-4 text-red-400 shrink-0" />
                          ) : isWarn ? (
                            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                          ) : (
                            <Info className="w-4 h-4 text-sky-400 shrink-0" />
                          )}
                          <span className="text-xs font-mono font-bold text-zinc-200">
                            {f.rule_id}
                          </span>
                          <span className="text-[11px] text-zinc-400 font-mono">
                            [{f.category}]
                          </span>
                        </div>
                        <Badge
                          variant="outline"
                          className={`text-[9px] font-mono ${
                            isUnknown
                              ? "text-amber-400 border-amber-800 bg-amber-950/40"
                              : isErr
                              ? "text-red-400 border-red-800 bg-red-950/40"
                              : "text-zinc-400 border-zinc-700"
                          }`}
                        >
                          {f.status}
                        </Badge>
                      </div>

                      <p className="text-xs text-zinc-300 mt-1.5 leading-relaxed">
                        {f.message}
                      </p>

                      {f.suggested_action && (
                        <div className="mt-2 text-[11px] text-sky-300/90 bg-sky-950/30 border border-sky-900/40 rounded px-2 py-1 flex items-center gap-1.5">
                          <Sparkles className="w-3 h-3 text-sky-400 shrink-0" />
                          <span>Action: {f.suggested_action}</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {activeSubTab === "stackup" && (
          <div className="space-y-3">
            <div className="text-xs text-zinc-400 font-mono">
              Board Layer Stackup Specification (Physical Copper & Dielectric)
            </div>
            {board?.layers && board.layers.length > 0 ? (
              <div className="border border-zinc-800 rounded-lg overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-zinc-900 text-zinc-400 font-mono text-[10px] border-b border-zinc-800">
                    <tr>
                      <th className="py-2 px-3">Order</th>
                      <th className="py-2 px-3">Layer Name</th>
                      <th className="py-2 px-3">Type</th>
                      <th className="py-2 px-3 text-right">Copper</th>
                      <th className="py-2 px-3 text-right">Dielectric</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800 font-mono text-[11px]">
                    {board.layers.map((l) => (
                      <tr key={l.id} className="hover:bg-zinc-900/40">
                        <td className="py-2 px-3 text-zinc-500">{l.layer_order}</td>
                        <td className="py-2 px-3 text-zinc-200 font-semibold">{l.layer_name}</td>
                        <td className="py-2 px-3">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] ${
                              l.layer_type === "PLANE"
                                ? "bg-amber-950/60 text-amber-300 border border-amber-800"
                                : "bg-sky-950/60 text-sky-300 border border-sky-800"
                            }`}
                          >
                            {l.layer_type}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right text-zinc-300">
                          {l.copper_thickness_um ? `${l.copper_thickness_um} µm` : "—"}
                        </td>
                        <td className="py-2 px-3 text-right text-zinc-400">
                          {l.dielectric_thickness_um ? `${l.dielectric_thickness_um} µm` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-6 text-center text-xs text-zinc-500">
                Default 2-layer FR-4 stackup (Top Layer, Bottom Layer with 35µm copper).
              </div>
            )}
          </div>
        )}

        {activeSubTab === "proposals" && (
          <div className="space-y-3">
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-md p-2.5 text-[11px] text-zinc-400 flex items-center justify-between">
              <span>Human Approval Gate: Autonomous layout mutation is disabled.</span>
              <span className="font-mono text-zinc-500">AUTONOMOUS_MUTATION = OFF</span>
            </div>

            {proposals && proposals.length > 0 ? (
              <div className="space-y-2">
                {proposals.map((prop) => (
                  <div
                    key={prop.id}
                    className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-3 space-y-2"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-xs font-semibold text-zinc-200">{prop.title}</div>
                        <div className="text-[11px] text-zinc-400 mt-0.5">{prop.description}</div>
                      </div>
                      <Badge
                        variant="outline"
                        className={`text-[9px] font-mono ${
                          prop.status === "APPLIED"
                            ? "text-emerald-400 border-emerald-800 bg-emerald-950/40"
                            : prop.status === "APPROVED"
                            ? "text-sky-400 border-sky-800 bg-sky-950/40"
                            : "text-amber-400 border-amber-800 bg-amber-950/40"
                        }`}
                      >
                        {prop.status}
                      </Badge>
                    </div>

                    {prop.diff_preview && (
                      <div className="bg-zinc-950 p-2 rounded border border-zinc-800/80 text-[11px] font-mono space-y-1">
                        <div className="text-zinc-500 text-[10px]">Deterministic Diff:</div>
                        {prop.diff_preview.summary.map((line, lidx) => (
                          <div key={lidx} className="text-zinc-300">
                            • {line}
                          </div>
                        ))}
                      </div>
                    )}

                    {prop.status === "STAGED" && (
                      <div className="flex items-center justify-end gap-2 pt-1">
                        <Button
                          size="sm"
                          onClick={() => approveMutation.mutate(prop.id)}
                          disabled={approveMutation.isPending}
                          className="h-7 px-3 text-xs bg-emerald-700 hover:bg-emerald-600 text-white font-medium flex items-center gap-1"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Approve & Apply</span>
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-6 text-center text-xs text-zinc-500">
                No active layout proposals staged for human review.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
