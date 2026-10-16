"use client";

import React, { useState, useEffect } from "react";
import {
  Lightbulb,
  CheckCircle2,
  AlertTriangle,
  Layers,
  ArrowRight,
  ShieldCheck,
  Zap,
  Sliders,
  Sparkles,
  Loader2,
  Plus,
  Table,
  Check,
  X,
  HelpCircle,
  TrendingDown,
  Cpu,
  Info,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  CircuitAnalysis,
  FindingItem,
  EngineeringDesignAlternative,
  DesignComparisonResponse,
  EngineeringConstraint,
  ComparisonMatrixRow,
} from "./types";

interface DesignIntelligenceTabProps {
  circuitId: string | null;
  analysis: CircuitAnalysis | null;
  initialFinding?: FindingItem | null;
  onProposalCreated: () => void;
}

export function DesignIntelligenceTab({
  circuitId,
  analysis,
  initialFinding,
  onProposalCreated,
}: DesignIntelligenceTabProps) {
  const [objectiveType, setObjectiveType] = useState<string>("RESOLVE_FINDING");
  const [title, setTitle] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [selectedFindingIds, setSelectedFindingIds] = useState<string[]>([]);
  const [constraints, setConstraints] = useState<EngineeringConstraint[]>([
    {
      name: "Max Component Power",
      constraint_type: "MAX_POWER",
      max_value: 0.5,
      unit: "W",
      is_hard_constraint: true,
    },
  ]);

  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isComparing, setIsComparing] = useState<boolean>(false);
  const [isPromoting, setIsPromoting] = useState<string | null>(null);
  const [alternatives, setAlternatives] = useState<EngineeringDesignAlternative[]>([]);
  const [comparison, setComparison] = useState<DesignComparisonResponse | null>(null);
  const [viewMode, setViewMode] = useState<"cards" | "matrix">("cards");
  const [expandedProvenanceId, setExpandedProvenanceId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Initialize or respond to initialFinding passed from Analysis tab
  useEffect(() => {
    if (initialFinding) {
      setObjectiveType("RESOLVE_FINDING");
      setTitle(`Resolve ${initialFinding.rule_id}: ${initialFinding.title}`);
      setDescription(initialFinding.recommended_action || initialFinding.description);
      setSelectedFindingIds([initialFinding.id]);
    } else if (analysis?.findings && analysis.findings.length > 0 && selectedFindingIds.length === 0) {
      const firstFinding = analysis.findings[0];
      if (firstFinding) {
        setTitle(`Mitigate ${firstFinding.rule_id}: ${firstFinding.title}`);
        setSelectedFindingIds([firstFinding.id]);
      }
    }
  }, [initialFinding, analysis]);

  const handleToggleFinding = (id: string) => {
    setSelectedFindingIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleAddConstraint = () => {
    setConstraints((prev) => [
      ...prev,
      {
        name: `Constraint ${prev.length + 1}`,
        constraint_type: "MAX_POWER",
        max_value: 0.25,
        unit: "W",
        is_hard_constraint: true,
      },
    ]);
  };

  const handleGenerateAlternatives = async () => {
    if (!circuitId) {
      setErrorMessage("No active circuit selected for design exploration.");
      return;
    }
    setIsGenerating(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const token = localStorage.getItem("token") || "";
      const res = await fetch(`/api/v1/circuits/${circuitId}/design/alternatives`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          title: title || `Design Exploration for Circuit`,
          description: description || "Automated design exploration",
          objective_type: objectiveType,
          target_finding_ids: selectedFindingIds,
          constraints: constraints,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to generate design alternatives.");
      }

      const raw = await res.json();
      const data: EngineeringDesignAlternative[] = raw.data || raw;
      setAlternatives(data);

      if (data.length > 0) {
        // Automatically fetch side-by-side comparison matrix
        handleFetchComparison(data);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to generate design alternatives");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleFetchComparison = async (currentAlts?: EngineeringDesignAlternative[]) => {
    if (!circuitId) return;
    setIsComparing(true);
    try {
      const token = localStorage.getItem("token") || "";
      const altsToCompare = currentAlts || alternatives;
      const res = await fetch(`/api/v1/circuits/${circuitId}/design/compare`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          alternatives: altsToCompare,
        }),
      });

      if (res.ok) {
        const compRaw = await res.json();
        const compData: DesignComparisonResponse = compRaw.data || compRaw;
        setComparison(compData);
      }
    } catch (err) {
      console.error("Failed to compare alternatives", err);
    } finally {
      setIsComparing(false);
    }
  };

  const handlePromoteToProposal = async (alt: EngineeringDesignAlternative) => {
    if (!circuitId) {
      setErrorMessage("No active circuit selected.");
      return;
    }
    const altId = alt.alternative_id || alt.id;
    setIsPromoting(altId);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const token = localStorage.getItem("token") || "";
      const res = await fetch(`/api/v1/circuits/${circuitId}/design/propose`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          alternative: alt,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const msg = typeof err.detail === "object" ? err.detail.message : err.detail;
        throw new Error(msg || "Failed to promote alternative to proposal.");
      }

      const resJson = await res.json();
      const proposal = resJson.data || resJson;
      setSuccessMessage(`Successfully staged proposal: "${proposal.title}". View in Staged Proposals queue.`);
      onProposalCreated();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to promote alternative to proposal");
    } finally {
      setIsPromoting(null);
    }
  };

  const getCandidateLabel = (index: number) => {
    const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    return `Candidate ${letters[index % letters.length] || index + 1}`;
  };

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-y-auto space-y-4">
      {/* Header */}
      <div className="p-4 border-b border-zinc-800/80 bg-zinc-900/60 sticky top-0 z-10 backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Lightbulb className="w-4 h-4 text-amber-400" />
            <h3 className="font-semibold text-sm tracking-wide text-zinc-100">
              Engineering Design Intelligence
            </h3>
          </div>
          {alternatives.length > 0 && (
            <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 p-0.5 rounded text-xs">
              <button
                onClick={() => setViewMode("cards")}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                  viewMode === "cards" ? "bg-zinc-800 text-amber-400" : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                Candidates
              </button>
              <button
                onClick={() => setViewMode("matrix")}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                  viewMode === "matrix" ? "bg-zinc-800 text-amber-400" : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                Comparison Matrix
              </button>
            </div>
          )}
        </div>
        <p className="text-[11px] text-zinc-400 mt-1">
          Explore technically grounded alternatives, verify constraints, inspect provenance, and decide which design to promote.
        </p>
      </div>

      <div className="p-4 space-y-4">
        {/* Alerts */}
        {errorMessage && (
          <div className="p-3 bg-red-950/50 border border-red-800 text-red-300 text-xs rounded-lg flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {successMessage && (
          <div className="p-3 bg-emerald-950/50 border border-emerald-800 text-emerald-300 text-xs rounded-lg flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Section 1: Objective & Constraints Definition */}
        <Card className="border-zinc-800 bg-zinc-900/40">
          <CardHeader className="p-3 pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-sky-400" />
                Engineering Objective & Constraints
              </CardTitle>
              <Badge variant="outline" className="text-[10px] text-zinc-400 border-zinc-700">
                Sandbox Simulation
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-3 pt-0 space-y-3">
            <div>
              <label className="text-[11px] text-zinc-400 block mb-1">Objective Type</label>
              <select
                value={objectiveType}
                onChange={(e) => setObjectiveType(e.target.value)}
                className="w-full h-8 px-2 bg-zinc-950 border border-zinc-700 rounded text-xs text-zinc-200 focus:outline-none focus:border-amber-500"
              >
                <option value="RESOLVE_FINDING">Resolve Finding(s) / Rating Violations</option>
                <option value="REDUCE_POWER">Reduce Circuit Power Dissipation</option>
                <option value="OPTIMIZE_MARGIN">Optimize Safety Margins</option>
                <option value="COMPONENT_REPLACEMENT">Standard Value & Package Upgrade</option>
                <option value="ISOLATE_DOMAINS">Isolate Voltage Domains (Regulator Upgrade)</option>
                <option value="ADD_DECOUPLING">Add Decoupling Capacitance</option>
                <option value="CUSTOM">Custom Objective</option>
              </select>
            </div>

            <div>
              <label className="text-[11px] text-zinc-400 block mb-1">Objective Goal</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Mitigate R003 resistor power overload"
                className="w-full h-8 px-2 bg-zinc-950 border border-zinc-700 rounded text-xs text-zinc-200 focus:outline-none focus:border-amber-500"
              />
            </div>

            {/* Target Findings Selector */}
            {analysis?.findings && analysis.findings.length > 0 && (
              <div>
                <label className="text-[11px] text-zinc-400 block mb-1.5">
                  Target Findings to Resolve ({analysis.findings.length} available)
                </label>
                <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                  {analysis.findings.map((f) => {
                    const isSelected = selectedFindingIds.includes(f.id);
                    return (
                      <div
                        key={f.id}
                        onClick={() => handleToggleFinding(f.id)}
                        className={`p-2 rounded border cursor-pointer text-xs flex items-center justify-between transition-colors ${
                          isSelected
                            ? "bg-amber-950/40 border-amber-700/80 text-amber-200"
                            : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700"
                        }`}
                      >
                        <div className="flex items-center gap-2 overflow-hidden">
                          <span className="font-mono text-[10px] font-bold px-1 py-0.5 rounded bg-zinc-800 text-zinc-300">
                            {f.rule_id}
                          </span>
                          <span className="truncate">{f.title}</span>
                        </div>
                        <div className="shrink-0 ml-2">
                          {isSelected ? (
                            <Check className="w-3.5 h-3.5 text-amber-400" />
                          ) : (
                            <div className="w-3.5 h-3.5 border border-zinc-700 rounded" />
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Active Constraints */}
            <div className="pt-1">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-medium text-zinc-300">Hard & Soft Constraints</span>
                <button
                  type="button"
                  onClick={handleAddConstraint}
                  className="text-[10px] text-sky-400 hover:text-sky-300 flex items-center gap-1"
                >
                  <Plus className="w-3 h-3" /> Add Constraint
                </button>
              </div>

              <div className="space-y-1.5">
                {constraints.map((c, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-2 p-2 bg-zinc-950 border border-zinc-800 rounded text-xs"
                  >
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span className="font-medium text-zinc-200">{c.name}:</span>
                    <span className="text-zinc-400">
                      {c.max_value !== undefined && c.max_value !== null ? `≤ ${c.max_value} ${c.unit || ""}` : ""}
                    </span>
                    <Badge
                      variant="outline"
                      className={`ml-auto text-[9px] px-1 py-0 font-bold ${
                        c.is_hard_constraint
                          ? "border-red-800/80 text-red-300 bg-red-950/40"
                          : "border-sky-800 text-sky-300"
                      }`}
                    >
                      {c.is_hard_constraint ? "HARD" : "SOFT"}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>

            <Button
              onClick={handleGenerateAlternatives}
              disabled={isGenerating}
              className="w-full h-8 bg-amber-600 hover:bg-amber-500 text-white font-medium text-xs flex items-center justify-center gap-2 mt-2"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Evaluating Alternatives in Sandbox...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Generate Design Alternatives</span>
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Section 2: Results View (Cards or Matrix) */}
        {alternatives.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-amber-400" />
                Design Alternatives ({alternatives.length})
              </h4>
              <Badge variant="outline" className="text-[10px] text-zinc-400 border-zinc-700">
                Transparent Comparison
              </Badge>
            </div>

            {/* MATRIX VIEW */}
            {viewMode === "matrix" && comparison && (
              <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900/30">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-zinc-900/80 text-zinc-400 border-b border-zinc-800 text-[11px] font-medium">
                      <tr>
                        <th className="p-2.5">Candidate</th>
                        <th className="p-2.5">Strategy</th>
                        <th className="p-2.5">Hard Constraints</th>
                        <th className="p-2.5">Soft Constraints</th>
                        <th className="p-2.5">Resolved</th>
                        <th className="p-2.5">Introduced</th>
                        <th className="p-2.5">Power Δ</th>
                        <th className="p-2.5">Components Δ</th>
                        <th className="p-2.5">Footprint</th>
                        <th className="p-2.5">Cost</th>
                        <th className="p-2.5">Confidence</th>
                        <th className="p-2.5">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60 font-mono text-[11px]">
                      {(comparison.comparison_matrix || []).map((row, idx) => {
                        const alt = alternatives.find(
                          (a) => (a.alternative_id || a.id) === row.alternative_id
                        );
                        const label = getCandidateLabel(idx);
                        return (
                          <tr key={row.alternative_id} className="hover:bg-zinc-800/40 transition-colors">
                            <td className="p-2.5 font-sans font-medium text-zinc-200">
                              <div>
                                <span className="text-amber-400 font-semibold">{label}</span>
                                <div className="text-[10px] text-zinc-400 truncate max-w-[120px]">{row.title}</div>
                              </div>
                            </td>
                            <td className="p-2.5 font-sans text-zinc-400 text-[10px]">{row.strategy}</td>
                            <td className="p-2.5">
                              {row.hard_constraints === "PASS" ? (
                                <span className="text-emerald-400 flex items-center gap-1 font-sans">
                                  <Check className="w-3 h-3" /> PASS
                                </span>
                              ) : row.hard_constraints === "FAIL" ? (
                                <span className="text-red-400 flex items-center gap-1 font-sans">
                                  <X className="w-3 h-3" /> FAIL
                                </span>
                              ) : (
                                <span className="text-amber-400 flex items-center gap-1 font-sans">
                                  <HelpCircle className="w-3 h-3" /> UNKNOWN
                                </span>
                              )}
                            </td>
                            <td className="p-2.5 text-zinc-300 font-sans text-[10px]">
                              {row.soft_constraints}
                            </td>
                            <td className="p-2.5 text-emerald-400">
                              +{row.findings_resolved_count}
                            </td>
                            <td className="p-2.5 text-rose-400">
                              {row.findings_introduced_count > 0 ? `+${row.findings_introduced_count}` : "0"}
                            </td>
                            <td className="p-2.5 text-zinc-300">
                              {row.power_delta_w !== null && row.power_delta_w !== undefined
                                ? `${row.power_delta_w > 0 ? "+" : ""}${row.power_delta_w.toFixed(2)}W`
                                : "UNKNOWN"}
                            </td>
                            <td className="p-2.5 text-zinc-300">
                              {row.component_count_delta > 0 ? `+${row.component_count_delta}` : `${row.component_count_delta}`}
                            </td>
                            <td className="p-2.5 text-zinc-400 font-sans text-[10px]">
                              {row.footprint}
                            </td>
                            <td className="p-2.5 text-zinc-400 font-sans text-[10px]">
                              {row.cost}
                            </td>
                            <td className="p-2.5">
                              <span
                                className={`text-[10px] font-sans font-semibold ${
                                  row.confidence === "HIGH" ? "text-emerald-400" : "text-amber-400"
                                }`}
                              >
                                {row.confidence}
                              </span>
                            </td>
                            <td className="p-2.5">
                              {alt && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={isPromoting === (alt.alternative_id || alt.id)}
                                  onClick={() => handlePromoteToProposal(alt)}
                                  className="h-6 text-[10px] border-amber-700/80 bg-amber-950/40 text-amber-300 hover:bg-amber-900/60"
                                >
                                  {isPromoting === (alt.alternative_id || alt.id) ? (
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                  ) : (
                                    "Propose"
                                  )}
                                </Button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* CARDS VIEW */}
            {viewMode === "cards" && (
              <div className="space-y-3">
                {alternatives.map((alt, idx) => {
                  const altId = alt.alternative_id || alt.id;
                  const label = getCandidateLabel(idx);
                  const isProvenanceExpanded = expandedProvenanceId === altId;

                  return (
                    <Card key={altId} className="border-zinc-800 bg-zinc-900/40">
                      <CardHeader className="p-3 pb-2">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">
                              {label}
                            </span>
                            <CardTitle className="text-xs font-semibold text-zinc-100">{alt.title}</CardTitle>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Badge
                              variant="outline"
                              className={`text-[9px] font-bold ${
                                alt.confidence === "HIGH"
                                  ? "border-emerald-800 text-emerald-400 bg-emerald-950/30"
                                  : "border-amber-800 text-amber-400 bg-amber-950/30"
                              }`}
                            >
                              {alt.confidence} EVIDENCE
                            </Badge>
                            <Badge
                              variant="outline"
                              className={`text-[9px] font-mono ${
                                alt.hard_constraints_status === "PASS"
                                  ? "border-emerald-800 text-emerald-300"
                                  : alt.hard_constraints_status === "FAIL"
                                  ? "border-red-800 text-red-300"
                                  : "border-amber-800 text-amber-300"
                              }`}
                            >
                              HARD: {alt.hard_constraints_status || "PASS"}
                            </Badge>
                          </div>
                        </div>
                        <CardDescription className="text-xs text-zinc-400 mt-1">
                          {alt.description}
                        </CardDescription>
                      </CardHeader>

                      <CardContent className="p-3 pt-0 space-y-3 text-xs">
                        {/* Proposed Changes */}
                        <div className="bg-zinc-950/60 p-2.5 rounded border border-zinc-800/80 space-y-1.5">
                          <span className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider block">
                            Specific Modifications ({alt.proposed_changes.length})
                          </span>
                          <ul className="space-y-1 text-[11px]">
                            {alt.proposed_changes.map((chg, i) => (
                              <li key={i} className="flex items-center gap-1.5 text-zinc-300 font-mono">
                                <ArrowRight className="w-3 h-3 text-amber-400 shrink-0" />
                                <span className="text-sky-300 font-semibold">{chg.operation || chg.change_type}</span>:{" "}
                                {chg.ref_des ? <span className="text-emerald-300">[{chg.ref_des}]</span> : null}{" "}
                                {chg.old_value !== undefined && chg.old_value !== null ? (
                                  <span className="line-through text-zinc-500 mr-1">{String(chg.old_value)}</span>
                                ) : null}
                                <span className="text-amber-200 font-bold">{String(chg.new_value)}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* Findings Resolved vs Introduced vs Remaining */}
                        <div className="grid grid-cols-3 gap-2 text-[11px]">
                          <div className="p-2 rounded bg-emerald-950/20 border border-emerald-900/40">
                            <span className="text-[10px] font-bold text-emerald-400 uppercase block mb-1">
                              Resolved ({alt.findings_resolved.length})
                            </span>
                            {alt.findings_resolved.length === 0 ? (
                              <span className="text-zinc-500 text-[10px]">None closed</span>
                            ) : (
                              alt.findings_resolved.map((rId, rIndex) => (
                                <div key={rIndex} className="text-emerald-300 font-mono text-[10px] truncate">
                                  ✓ {rId}
                                </div>
                              ))
                            )}
                          </div>

                          <div className="p-2 rounded bg-rose-950/20 border border-rose-900/40">
                            <span className="text-[10px] font-bold text-rose-400 uppercase block mb-1">
                              Introduced ({alt.findings_introduced.length})
                            </span>
                            {alt.findings_introduced.length === 0 ? (
                              <span className="text-emerald-400 text-[10px]">0 new</span>
                            ) : (
                              alt.findings_introduced.map((iId, iIndex) => (
                                <div key={iIndex} className="text-rose-300 font-mono text-[10px] truncate">
                                  ⚠ {iId}
                                </div>
                              ))
                            )}
                          </div>

                          <div className="p-2 rounded bg-zinc-950 border border-zinc-800">
                            <span className="text-[10px] font-bold text-zinc-400 uppercase block mb-1">
                              Remaining ({(alt.remaining_findings || []).length})
                            </span>
                            {(alt.remaining_findings || []).length === 0 ? (
                              <span className="text-zinc-500 text-[10px]">0 remaining</span>
                            ) : (
                              (alt.remaining_findings || []).map((remId, remIndex) => (
                                <div key={remIndex} className="text-zinc-400 font-mono text-[10px] truncate">
                                  • {remId}
                                </div>
                              ))
                            )}
                          </div>
                        </div>

                        {/* Constraint Verification Results */}
                        <div>
                          <span className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider block mb-1">
                            Constraint Checks
                          </span>
                          <div className="space-y-1">
                            {alt.constraint_results.map((cr, cIndex) => {
                              const isPass = cr.status === "PASS" || cr.status === "SATISFIED";
                              const isFail = cr.status === "FAIL" || cr.status === "NOT_SATISFIED";
                              return (
                                <div
                                  key={cIndex}
                                  className={`flex items-center justify-between p-1.5 rounded text-[11px] border ${
                                    isPass
                                      ? "bg-zinc-950 border-zinc-800 text-zinc-300"
                                      : isFail
                                      ? "bg-red-950/30 border-red-900/60 text-red-300"
                                      : "bg-amber-950/30 border-amber-900/60 text-amber-300"
                                  }`}
                                >
                                  <div className="flex items-center gap-1.5">
                                    {isPass ? (
                                      <Check className="w-3 h-3 text-emerald-400" />
                                    ) : isFail ? (
                                      <X className="w-3 h-3 text-red-400" />
                                    ) : (
                                      <HelpCircle className="w-3 h-3 text-amber-400" />
                                    )}
                                    <span>{cr.constraint_name}</span>
                                  </div>
                                  <div className="flex items-center gap-2">
                                    {cr.actual_value !== undefined && cr.actual_value !== null && (
                                      <span className="font-mono text-[10px] text-zinc-400">
                                        {String(cr.actual_value)}
                                      </span>
                                    )}
                                    <Badge
                                      variant="outline"
                                      className={`text-[8px] px-1 py-0 ${
                                        cr.hard_or_soft === "HARD" || cr.is_hard
                                          ? "text-red-400 border-red-800"
                                          : "text-sky-400 border-sky-800"
                                      }`}
                                    >
                                      {cr.status} ({cr.hard_or_soft || (cr.is_hard ? "HARD" : "SOFT")})
                                    </Badge>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>

                        {/* Trade-offs */}
                        {alt.tradeoffs && alt.tradeoffs.length > 0 && (
                          <div className="p-2 rounded bg-zinc-950 border border-zinc-800/80">
                            <span className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider block mb-1">
                              Engineering Trade-offs
                            </span>
                            <ul className="list-disc list-inside space-y-0.5 text-zinc-300 text-[11px]">
                              {alt.tradeoffs.map((t, tidx) => (
                                <li key={tidx}>{t}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Auditable Provenance Inspector */}
                        <div className="border border-zinc-800 rounded bg-zinc-950/40 p-2">
                          <button
                            type="button"
                            onClick={() => setExpandedProvenanceId(isProvenanceExpanded ? null : altId)}
                            className="w-full flex items-center justify-between text-[10px] font-mono text-zinc-400 hover:text-zinc-200"
                          >
                            <span className="flex items-center gap-1">
                              <Info className="w-3 h-3 text-sky-400" />
                              Auditable Candidate Provenance Chain
                            </span>
                            {isProvenanceExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          </button>

                          {isProvenanceExpanded && (
                            <div className="mt-2 pt-2 border-t border-zinc-800 font-mono text-[10px] text-zinc-400 space-y-1">
                              <div><span className="text-zinc-300">Trigger:</span> {alt.candidate_provenance?.trigger || "Rule Engine Finding"}</div>
                              <div><span className="text-zinc-300">Strategy:</span> {alt.candidate_provenance?.generation_strategy || "Parameter Derivation"}</div>
                              <div><span className="text-zinc-300">Sources:</span> {(alt.candidate_provenance?.knowledge_sources || alt.provenance || []).join(", ")}</div>
                              <div><span className="text-zinc-300">Footprint:</span> {alt.footprint || "UNKNOWN"}</div>
                              <div><span className="text-zinc-300">Cost:</span> {alt.cost || "UNKNOWN"}</div>
                            </div>
                          )}
                        </div>

                        {/* Promote to Formal Proposal CTA */}
                        <div className="pt-1 flex items-center justify-between">
                          <span className="text-[10px] text-zinc-500 font-mono">
                            Stage into revision-bound proposal queue
                          </span>
                          <Button
                            onClick={() => handlePromoteToProposal(alt)}
                            disabled={isPromoting === altId}
                            size="sm"
                            className="h-7 text-xs bg-amber-600 hover:bg-amber-500 text-white font-medium flex items-center gap-1.5"
                          >
                            {isPromoting === altId ? (
                              <>
                                <Loader2 className="w-3 h-3 animate-spin" />
                                <span>Staging...</span>
                              </>
                            ) : (
                              <>
                                <Sparkles className="w-3 h-3" />
                                <span>Promote {label} to Proposal</span>
                              </>
                            )}
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
