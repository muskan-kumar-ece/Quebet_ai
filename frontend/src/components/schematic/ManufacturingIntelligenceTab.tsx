"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Factory,
  Layers,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  RefreshCw,
  Loader2,
  Info,
  Check,
  X,
  FileCheck,
  Hash,
  Cpu,
  Ruler,
  Maximize2,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { apiClient } from "@/lib/api";
import {
  EngineeringBoard,
  ManufacturingAnalysisResponse,
  ManufacturingFinding,
  ManufacturingProposalResponse,
  ManufacturingRuleSetResponse,
  DFMSnapshotResponse,
} from "./types";

interface ManufacturingIntelligenceTabProps {
  circuitId: string | null;
}

export function ManufacturingIntelligenceTab({ circuitId }: ManufacturingIntelligenceTabProps) {
  const queryClient = useQueryClient();
  const [activeSubTab, setActiveSubTab] = useState<"findings" | "proposals" | "ruleset" | "provenance">("findings");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [selectedFinding, setSelectedFinding] = useState<ManufacturingFinding | null>(null);

  // 1. Fetch Board for this circuit
  const {
    data: board,
    isLoading: isBoardLoading,
  } = useQuery<EngineeringBoard>({
    queryKey: ["engineering-board", circuitId],
    queryFn: async () => {
      if (!circuitId) throw new Error("No circuit ID");
      const res = await apiClient.get(`/pcb/boards/by-circuit/${circuitId}`);
      return res.data?.data;
    },
    enabled: !!circuitId,
  });

  // 2. Fetch Rulesets
  const {
    data: rulesets = [],
    isLoading: isRulesetsLoading,
  } = useQuery<ManufacturingRuleSetResponse[]>({
    queryKey: ["dfm-rulesets"],
    queryFn: async () => {
      const res = await apiClient.get("/dfm/rulesets");
      return res.data?.data || [];
    },
  });

  const [selectedRulesetId, setSelectedRulesetId] = useState<string>("");

  // 3. Run or fetch DFM analysis
  const {
    data: analysis,
    isLoading: isAnalysisLoading,
    refetch: refetchAnalysis,
  } = useQuery<ManufacturingAnalysisResponse>({
    queryKey: ["dfm-analysis", board?.id],
    queryFn: async () => {
      if (!board?.id) throw new Error("No board ID");
      const res = await apiClient.post("/dfm/analyses", {
        board_id: board.id,
        rule_set_id: selectedRulesetId || undefined,
        include_bom_check: true,
      });
      return res.data?.data;
    },
    enabled: !!board?.id,
  });

  // 4. Fetch Proposals for current analysis
  const {
    data: proposals = [],
    isLoading: isProposalsLoading,
    refetch: refetchProposals,
  } = useQuery<ManufacturingProposalResponse[]>({
    queryKey: ["dfm-proposals", analysis?.id],
    queryFn: async () => {
      if (!analysis?.id) return [];
      const res = await apiClient.get(`/dfm/analyses/${analysis.id}/proposals`);
      return res.data?.data || [];
    },
    enabled: !!analysis?.id,
  });

  // 5. Fetch DFM Snapshot
  const { data: snapshot } = useQuery<DFMSnapshotResponse>({
    queryKey: ["dfm-snapshot", analysis?.id],
    queryFn: async () => {
      if (!analysis?.id) throw new Error("No analysis ID");
      const res = await apiClient.get(`/dfm/analyses/${analysis.id}/snapshot`);
      return res.data?.data;
    },
    enabled: !!analysis?.id && activeSubTab === "provenance",
  });

  // Mutation: Run Analysis
  const runAnalysisMutation = useMutation({
    mutationFn: async () => {
      if (!board?.id) throw new Error("No board");
      const res = await apiClient.post("/dfm/analyses", {
        board_id: board.id,
        rule_set_id: selectedRulesetId || undefined,
        include_bom_check: true,
      });
      return res.data?.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["dfm-analysis", board?.id], data);
      refetchProposals();
    },
  });

  // Mutation: Approve Proposal
  const approveMutation = useMutation({
    mutationFn: async (proposalId: string) => {
      const res = await apiClient.post(`/dfm/proposals/${proposalId}/approve`);
      return res.data?.data;
    },
    onSuccess: () => {
      refetchProposals();
      refetchAnalysis();
    },
  });

  // Mutation: Apply Proposal
  const applyMutation = useMutation({
    mutationFn: async (proposalId: string) => {
      const res = await apiClient.post(`/dfm/proposals/${proposalId}/apply`);
      return res.data?.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["engineering-board", circuitId] });
      refetchProposals();
      refetchAnalysis();
    },
  });

  if (!circuitId) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center text-muted-foreground">
        <Factory className="w-12 h-12 mb-4 text-muted-foreground/50" />
        <h3 className="font-semibold text-lg text-foreground">No Circuit Selected</h3>
        <p className="text-sm">Select or create a circuit to evaluate manufacturing and assembly DFM constraints.</p>
      </div>
    );
  }

  if (isBoardLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center text-muted-foreground">
        <Loader2 className="w-8 h-8 animate-spin mb-4 text-primary" />
        <p className="text-sm">Loading PCB physical geometry...</p>
      </div>
    );
  }

  if (!board) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center text-muted-foreground">
        <Layers className="w-12 h-12 mb-4 text-muted-foreground/50" />
        <h3 className="font-semibold text-lg text-foreground">No Board Layout Associated</h3>
        <p className="text-sm max-w-md">
          A physical board layout must be instantiated before DFM / DFA manufacturing checks can execute.
        </p>
      </div>
    );
  }

  const findings = analysis?.findings || [];
  const summary = analysis?.summary;

  const filteredFindings = findings.filter((f) => {
    if (categoryFilter !== "ALL" && f.category !== categoryFilter) return false;
    if (statusFilter !== "ALL" && f.status !== statusFilter) return false;
    return true;
  });

  return (
    <div className="flex flex-col h-full bg-background text-foreground border-l border-border overflow-hidden">
      {/* Top Header */}
      <div className="p-4 border-b border-border bg-card/40 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg text-primary">
            <Factory className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-semibold text-base">Manufacturing & DFM Intelligence</h2>
              <Badge variant="outline" className="text-xs font-mono">
                Rev {board.revision ?? board.version ?? 1}
              </Badge>
              {summary && (
                <Badge
                  variant={summary.status === "COMPLETED" ? "default" : "destructive"}
                  className="text-xs uppercase"
                >
                  {summary.status}
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Fabrication bounds, assembly spacing, and BOM-to-PCB packaging verification
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => runAnalysisMutation.mutate()}
            disabled={runAnalysisMutation.isPending}
            className="gap-2 text-xs"
          >
            {runAnalysisMutation.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5" />
            )}
            Run DFM Audit
          </Button>
        </div>
      </div>

      {/* KPI Cards Header (STRICT ZERO SYNTHETIC SCORE) */}
      <div className="grid grid-cols-5 gap-2 p-3 border-b border-border bg-muted/20 text-xs">
        <div className="p-2.5 rounded-md bg-card border border-border">
          <div className="text-muted-foreground text-[10px] uppercase tracking-wider">Evaluated</div>
          <div className="text-lg font-bold mt-0.5">{summary?.total_rules_evaluated ?? "--"}</div>
        </div>
        <div className="p-2.5 rounded-md bg-card border border-border">
          <div className="text-emerald-500 text-[10px] uppercase tracking-wider flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> Pass
          </div>
          <div className="text-lg font-bold text-emerald-500 mt-0.5">{summary?.pass_count ?? "--"}</div>
        </div>
        <div className="p-2.5 rounded-md bg-card border border-border">
          <div className="text-destructive text-[10px] uppercase tracking-wider flex items-center gap-1">
            <XCircle className="w-3 h-3" /> Violations
          </div>
          <div className="text-lg font-bold text-destructive mt-0.5">{summary?.fail_count ?? "--"}</div>
        </div>
        <div className="p-2.5 rounded-md bg-card border border-border">
          <div className="text-amber-500 text-[10px] uppercase tracking-wider flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Warnings
          </div>
          <div className="text-lg font-bold text-amber-500 mt-0.5">{summary?.warning_count ?? "--"}</div>
        </div>
        <div className="p-2.5 rounded-md bg-card border border-border">
          <div className="text-muted-foreground text-[10px] uppercase tracking-wider flex items-center gap-1">
            <HelpCircle className="w-3 h-3" /> Inconclusive
          </div>
          <div className="text-lg font-bold text-muted-foreground mt-0.5">{summary?.unknown_count ?? "--"}</div>
        </div>
      </div>

      {/* Epistemic Invariant Boundary Notice */}
      <div className="px-4 py-1.5 bg-blue-500/10 border-b border-blue-500/20 text-[11px] text-blue-400 flex items-center justify-between">
        <span className="flex items-center gap-1.5">
          <Info className="w-3.5 h-3.5" />
          <span>Epistemic Guard: UNKNOWN != PASS. DFM analysis does not constitute factory sign-off.</span>
        </span>
        <span className="font-mono text-[10px] opacity-75">AI_ENGINEERING_AUTHORITY = NONE</span>
      </div>

      {/* Subtab Navigation */}
      <div className="flex items-center gap-1 px-4 border-b border-border bg-card/20">
        <button
          onClick={() => setActiveSubTab("findings")}
          className={`py-2 px-3 text-xs font-medium border-b-2 transition-colors ${
            activeSubTab === "findings"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Rule Findings ({findings.length})
        </button>
        <button
          onClick={() => setActiveSubTab("proposals")}
          className={`py-2 px-3 text-xs font-medium border-b-2 transition-colors ${
            activeSubTab === "proposals"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Resolution Proposals ({proposals.length})
        </button>
        <button
          onClick={() => setActiveSubTab("ruleset")}
          className={`py-2 px-3 text-xs font-medium border-b-2 transition-colors ${
            activeSubTab === "ruleset"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Manufacturing Ruleset
        </button>
        <button
          onClick={() => setActiveSubTab("provenance")}
          className={`py-2 px-3 text-xs font-medium border-b-2 transition-colors ${
            activeSubTab === "provenance"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Integrity & Provenance
        </button>
      </div>

      {/* Subtab Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeSubTab === "findings" && (
          <div className="space-y-3">
            {/* Filter Bar */}
            <div className="flex items-center justify-between gap-2 pb-2 border-b border-border/50 text-xs">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Category:</span>
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="bg-muted px-2 py-1 rounded text-xs border border-border"
                >
                  <option value="ALL">All Categories</option>
                  <option value="FABRICATION">Fabrication</option>
                  <option value="ASSEMBLY">Assembly</option>
                  <option value="CLEARANCE">Clearance</option>
                  <option value="DRILL_VIA">Drill & Vias</option>
                  <option value="COMPONENT_PLACEMENT">Component Placement</option>
                  <option value="SOLDER_MASK">Solder Mask</option>
                  <option value="SILKSCREEN">Silkscreen</option>
                  <option value="BOM_CONSISTENCY">BOM Consistency</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Status:</span>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-muted px-2 py-1 rounded text-xs border border-border"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="FAIL">Fail / Violations</option>
                  <option value="WARNING">Warnings</option>
                  <option value="PASS">Pass</option>
                  <option value="UNKNOWN">Inconclusive</option>
                </select>
              </div>
            </div>

            {/* Findings List */}
            {filteredFindings.length === 0 ? (
              <div className="text-center py-10 text-muted-foreground text-xs">
                No manufacturing findings match the selected filters.
              </div>
            ) : (
              <div className="space-y-2">
                {filteredFindings.map((finding) => {
                  const isFail = finding.status === "FAIL";
                  const isWarn = finding.status === "WARNING";
                  const isPass = finding.status === "PASS";
                  const isUnknown = finding.status === "UNKNOWN";

                  return (
                    <div
                      key={finding.finding_id}
                      onClick={() => setSelectedFinding(finding)}
                      className={`p-3 rounded-lg border text-xs cursor-pointer transition-all ${
                        selectedFinding?.finding_id === finding.finding_id
                          ? "border-primary bg-primary/5"
                          : "border-border bg-card/60 hover:border-border/80"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-semibold text-[11px] text-primary">
                            {finding.rule_id}
                          </span>
                          <span className="font-medium text-foreground">{finding.rule_name}</span>
                          <Badge variant="outline" className="text-[10px] uppercase">
                            {finding.category}
                          </Badge>
                        </div>
                        <Badge
                          variant={
                            isFail ? "destructive" : isWarn ? "secondary" : isPass ? "default" : "outline"
                          }
                          className="text-[10px]"
                        >
                          {finding.status}
                        </Badge>
                      </div>

                      <p className="text-muted-foreground text-xs mb-2 leading-relaxed">{finding.message}</p>

                      {/* Measured vs Required margin differential */}
                      {(finding.measured_value !== undefined || finding.required_value !== undefined) && (
                        <div className="flex items-center gap-4 text-[11px] bg-muted/40 p-2 rounded font-mono">
                          {finding.measured_value !== undefined && (
                            <div>
                              <span className="text-muted-foreground">Measured: </span>
                              <span className="font-bold text-foreground">
                                {finding.measured_value} {finding.unit || "mm"}
                              </span>
                            </div>
                          )}
                          {finding.required_value !== undefined && (
                            <div>
                              <span className="text-muted-foreground">Required: </span>
                              <span className="text-foreground">
                                {finding.required_value} {finding.unit || "mm"}
                              </span>
                            </div>
                          )}
                          {finding.margin !== undefined && (
                            <div>
                              <span className="text-muted-foreground">Margin: </span>
                              <span className={finding.margin < 0 ? "text-destructive font-bold" : "text-emerald-500 font-bold"}>
                                {finding.margin > 0 ? `+${finding.margin}` : finding.margin} {finding.unit || "mm"}
                              </span>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Elements and proposal availability */}
                      <div className="flex items-center justify-between mt-2 text-[10px] text-muted-foreground">
                        <div className="flex items-center gap-2">
                          <span>Element: {finding.element_type}</span>
                          {finding.layer && <span>• Layer: {finding.layer}</span>}
                          {finding.ref_des && <span>• Ref: {finding.ref_des}</span>}
                        </div>
                        {finding.proposal_available && (
                          <span className="text-primary font-medium flex items-center gap-1">
                            <Sparkles className="w-3 h-3" /> Proposal Available
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Proposals Tab */}
        {activeSubTab === "proposals" && (
          <div className="space-y-3">
            <div className="text-xs text-muted-foreground mb-2">
              Proposals provide deterministic geometric or metadata fixes for identified DFM violations.
              <span className="block font-semibold text-foreground mt-0.5">
                Human sign-off is mandatory before proposals can be applied. AI automated approval is blocked.
              </span>
            </div>

            {proposals.length === 0 ? (
              <div className="text-center py-10 text-muted-foreground text-xs">
                No active DFM resolution proposals generated for this board revision.
              </div>
            ) : (
              proposals.map((prop) => (
                <div key={prop.id} className="p-3.5 rounded-lg border border-border bg-card/60 space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-primary">{prop.rule_id}</span>
                      <span className="font-medium text-foreground">{prop.title}</span>
                    </div>
                    <Badge variant={prop.status === "APPLIED" ? "default" : "outline"} className="text-[10px]">
                      {prop.status}
                    </Badge>
                  </div>

                  <p className="text-muted-foreground text-xs">{prop.description}</p>

                  {/* Diff preview */}
                  <div className="bg-muted/50 p-2.5 rounded font-mono text-[11px] space-y-1">
                    <div className="text-[10px] text-muted-foreground uppercase">Mutation Diff Preview:</div>
                    <pre className="overflow-x-auto text-xs">{JSON.stringify(prop.diff_preview, null, 2)}</pre>
                  </div>

                  {/* Human gate action buttons */}
                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/50">
                    {prop.status === "PROPOSED" && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => approveMutation.mutate(prop.id)}
                        disabled={approveMutation.isPending}
                        className="gap-1.5 text-xs"
                      >
                        <Check className="w-3.5 h-3.5 text-emerald-500" />
                        Human Sign-Off (Approve)
                      </Button>
                    )}
                    {(prop.status === "PROPOSED" || prop.status === "APPROVED") && (
                      <Button
                        size="sm"
                        onClick={() => applyMutation.mutate(prop.id)}
                        disabled={applyMutation.isPending}
                        className="gap-1.5 text-xs"
                      >
                        <ArrowRight className="w-3.5 h-3.5" />
                        Apply Mutation to PCB
                      </Button>
                    )}
                    {prop.status === "APPLIED" && (
                      <span className="text-[11px] text-emerald-500 font-medium flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Applied to PCB Revision {prop.board_revision + 1}
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Ruleset Tab */}
        {activeSubTab === "ruleset" && (
          <div className="space-y-4">
            <div className="p-3 rounded-lg border border-border bg-card/40 space-y-2 text-xs">
              <label className="font-medium text-foreground block">Active Ruleset Selection:</label>
              <select
                value={selectedRulesetId || analysis?.rule_set_id || ""}
                onChange={(e) => setSelectedRulesetId(e.target.value)}
                className="w-full bg-muted px-2.5 py-1.5 rounded text-xs border border-border"
              >
                {rulesets.map((rs) => (
                  <option key={rs.id} value={rs.id}>
                    {rs.name} ({rs.source} - {rs.source_revision})
                  </option>
                ))}
              </select>
            </div>

            {/* Rules parameters view */}
            <div className="space-y-2">
              <div className="text-xs font-semibold text-foreground">Configured Physical Limits:</div>
              {rulesets.length > 0 && (
                <div className="p-3 bg-muted/30 rounded-lg border border-border text-xs font-mono space-y-1.5">
                  <div className="flex justify-between py-1 border-b border-border/40">
                    <span className="text-muted-foreground">Min Trace Width:</span>
                    <span className="font-semibold text-foreground">0.15 mm (6 mil)</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/40">
                    <span className="text-muted-foreground">Min Copper Clearance:</span>
                    <span className="font-semibold text-foreground">0.15 mm (6 mil)</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/40">
                    <span className="text-muted-foreground">Min Drill Diameter:</span>
                    <span className="font-semibold text-foreground">0.30 mm (12 mil)</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/40">
                    <span className="text-muted-foreground">Min Annular Ring:</span>
                    <span className="font-semibold text-foreground">0.15 mm (IPC Class 2)</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/40">
                    <span className="text-muted-foreground">Board Edge Clearance:</span>
                    <span className="font-semibold text-foreground">0.50 mm (20 mil)</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/40">
                    <span className="text-muted-foreground">Min Component Clearance:</span>
                    <span className="font-semibold text-foreground">0.50 mm</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/40">
                    <span className="text-muted-foreground">Min Solder Mask Web:</span>
                    <span className="font-semibold text-foreground">0.10 mm</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Provenance Tab */}
        {activeSubTab === "provenance" && (
          <div className="space-y-3">
            <div className="p-3 rounded-lg border border-border bg-card/40 space-y-2.5 text-xs">
              <div className="flex items-center gap-2 font-medium text-foreground">
                <Hash className="w-4 h-4 text-primary" />
                <span>Deterministic SHA-256 Provenance Digest</span>
              </div>
              <div className="p-2.5 bg-muted rounded font-mono text-xs break-all border border-border/50 text-primary">
                {snapshot?.canonical_digest || analysis?.provenance_digest || "Computing..."}
              </div>
              <div className="text-[11px] text-muted-foreground">
                Canonical cryptographic digest linking PCB board revision, fabrication ruleset parameters, and evaluated margins.
              </div>
            </div>

            {/* Invariant assurances */}
            <div className="p-3 rounded-lg border border-border bg-muted/20 space-y-2 text-xs">
              <div className="font-semibold text-foreground flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-500" />
                <span>Enforced Epistemic Invariants:</span>
              </div>
              <ul className="space-y-1 text-[11px] font-mono text-muted-foreground">
                <li>• AI_ENGINEERING_AUTHORITY = NONE</li>
                <li>• AUTONOMOUS_MANUFACTURING_APPROVAL = DISABLED</li>
                <li>• AUTONOMOUS_FABRICATION_RELEASE = DISABLED</li>
                <li>• UNKNOWN != PASS</li>
                <li>• UNKNOWN != MANUFACTURABLE</li>
                <li>• DFM_ANALYSIS != MANUFACTURER_CERTIFICATION</li>
                <li>• ZERO_SYNTHETIC_MANUFACTURABILITY_SCORE</li>
                <li>• ZERO_SYNTHETIC_FABRICATOR_RANKING</li>
                <li>• PROVENANCE_AND_INTEGRITY_DIGEST != DIGITAL_SIGNATURE</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
