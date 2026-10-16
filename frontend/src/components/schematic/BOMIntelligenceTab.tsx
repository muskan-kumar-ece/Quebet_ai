"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Package,
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
  DollarSign,
  TrendingDown,
  Building2,
  Check,
  X,
  FileCheck,
  Hash,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { apiClient } from "@/lib/api";
import {
  EngineeringBOM,
  EngineeringBOMLine,
  ComponentPartCandidate,
  BOMSubstitutionProposal,
  ParameterCompatibilityEvaluation,
} from "./types";

interface BOMIntelligenceTabProps {
  circuitId: string | null;
}

export function BOMIntelligenceTab({ circuitId }: BOMIntelligenceTabProps) {
  const queryClient = useQueryClient();
  const [activeSubTab, setActiveSubTab] = useState<"lines" | "candidates" | "supply" | "substitutions">("lines");
  const [selectedLineId, setSelectedLineId] = useState<string | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<ComponentPartCandidate | null>(null);

  // Fetch BOM for this circuit
  const {
    data: bom,
    isLoading: isBOMLoading,
    refetch: refetchBOM,
  } = useQuery<EngineeringBOM>({
    queryKey: ["engineering-bom", circuitId],
    queryFn: async () => {
      if (!circuitId) throw new Error("No circuit ID");
      const res = await apiClient.get(`/circuits/${circuitId}/bom`);
      return res.data?.data;
    },
    enabled: !!circuitId,
  });

  // Generate BOM mutation
  const generateBOMMutation = useMutation({
    mutationFn: async () => {
      if (!circuitId) return;
      const res = await apiClient.post("/boms", { circuit_id: circuitId });
      return res.data?.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["engineering-bom", circuitId] });
    },
  });

  // Evaluate BOM mutation
  const evaluateBOMMutation = useMutation({
    mutationFn: async () => {
      if (!bom?.id) return;
      const res = await apiClient.post(`/boms/${bom.id}/evaluate`);
      return res.data?.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["engineering-bom", circuitId] });
    },
  });

  // Approve substitution mutation
  const approveSubstitutionMutation = useMutation({
    mutationFn: async (proposalId: string) => {
      const res = await apiClient.post(`/boms/substitutions/${proposalId}/approve`);
      return res.data?.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["engineering-bom", circuitId] });
    },
  });

  const selectedLine = bom?.lines?.find((l) => l.id === selectedLineId) || bom?.lines?.[0];

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "SOURCED":
      case "ENGINEERING_COMPATIBLE":
      case "IN_STOCK":
      case "ACTIVE":
      case "APPROVED":
        return <Badge className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20">{status}</Badge>;
      case "CONFLICTING":
      case "LIMITED_STOCK":
      case "NRND":
      case "PARTIALLY_EVALUATED":
        return <Badge className="bg-amber-500/10 text-amber-500 border-amber-500/20">{status}</Badge>;
      case "INCOMPATIBLE":
      case "OUT_OF_STOCK":
      case "EOL":
      case "OBSOLETE":
      case "NOT_COMPATIBLE":
        return <Badge className="bg-rose-500/10 text-rose-500 border-rose-500/20">{status}</Badge>;
      case "UNKNOWN":
      case "UNMATCHED":
      default:
        return <Badge className="bg-zinc-500/10 text-zinc-400 border-zinc-500/20">{status}</Badge>;
    }
  };

  if (isBOMLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-2 text-sm text-muted-foreground">Loading BOM Intelligence...</span>
      </div>
    );
  }

  if (!bom) {
    return (
      <Card className="border-border/40 bg-background/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="h-5 w-5 text-primary" />
            Engineering Bill of Materials (BOM)
          </CardTitle>
          <CardDescription>
            Deterministic component procurement intelligence and engineering validation.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center p-8 space-y-4">
          <p className="text-sm text-muted-foreground text-center max-w-md">
            No BOM has been generated for this schematic yet. Generate a canonical BOM to extract engineering
            requirements and match manufacturer candidates.
          </p>
          <Button
            onClick={() => generateBOMMutation.mutate()}
            disabled={generateBOMMutation.isPending || !circuitId}
          >
            {generateBOMMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Generate Canonical BOM
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Non-negotiable Epistemic Invariants Banner */}
      <div className="rounded-md border border-amber-500/20 bg-amber-500/5 px-4 py-2 text-xs text-amber-500/90 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4" />
          <span>
            <strong>BOM BOUNDARY:</strong> AI ENGINEERING AUTHORITY = NONE | ZERO SYNTHETIC SCORING | AVAILABLE != COMPATIBLE | NO AUTONOMOUS PURCHASE
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono">Rev {bom.version}</span>
          {bom.integrity_digest && (
            <Badge variant="outline" className="font-mono text-[10px] bg-background">
              <Hash className="h-3 w-3 mr-1" />
              {bom.integrity_digest.substring(0, 12)}...
            </Badge>
          )}
        </div>
      </div>

      {/* Header Overview Card */}
      <Card className="border-border/40 bg-background/50">
        <CardHeader className="py-4">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="text-base flex items-center gap-2">
                <Package className="h-4 w-4 text-primary" />
                {bom.name}
                <Badge variant="outline">{bom.status}</Badge>
              </CardTitle>
              <CardDescription className="text-xs">
                Total lines: {bom.total_lines} | Circuit Version: {bom.circuit_version}
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => evaluateBOMMutation.mutate()}
                disabled={evaluateBOMMutation.isPending}
              >
                {evaluateBOMMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                Evaluate Compatibility
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Sub-tab Navigation */}
      <div className="flex border-b border-border/40 space-x-4">
        <button
          onClick={() => setActiveSubTab("lines")}
          className={`pb-2 text-sm font-medium transition-colors ${
            activeSubTab === "lines"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          BOM Lines ({bom.lines?.length || 0})
        </button>
        <button
          onClick={() => setActiveSubTab("candidates")}
          className={`pb-2 text-sm font-medium transition-colors ${
            activeSubTab === "candidates"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Procurement Candidates
        </button>
        <button
          onClick={() => setActiveSubTab("supply")}
          className={`pb-2 text-sm font-medium transition-colors ${
            activeSubTab === "supply"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Multi-Source Supply
        </button>
        <button
          onClick={() => setActiveSubTab("substitutions")}
          className={`pb-2 text-sm font-medium transition-colors ${
            activeSubTab === "substitutions"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Substitution Proposals ({bom.substitutions?.length || 0})
        </button>
      </div>

      {/* SUB-TAB 1: BOM LINES */}
      {activeSubTab === "lines" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2 space-y-2">
            <div className="rounded-md border border-border/40 overflow-hidden">
              <table className="w-full text-xs text-left">
                <thead className="bg-muted/50 border-b border-border/40 text-muted-foreground font-medium">
                  <tr>
                    <th className="p-2">RefDes</th>
                    <th className="p-2">Type</th>
                    <th className="p-2">Value</th>
                    <th className="p-2">Package</th>
                    <th className="p-2">Assigned MPN</th>
                    <th className="p-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  {bom.lines?.map((line) => (
                    <tr
                      key={line.id}
                      onClick={() => setSelectedLineId(line.id)}
                      className={`cursor-pointer hover:bg-muted/30 transition-colors ${
                        (selectedLineId === line.id || (!selectedLineId && line.id === bom.lines[0]?.id))
                          ? "bg-muted/40 font-medium"
                          : ""
                      }`}
                    >
                      <td className="p-2 font-mono">{line.reference_designator}</td>
                      <td className="p-2">{line.component_type}</td>
                      <td className="p-2">{line.design_value}</td>
                      <td className="p-2 font-mono text-[11px]">{line.design_package || line.footprint_name || "—"}</td>
                      <td className="p-2 font-mono text-[11px]">{line.manufacturer_part_number || "Unassigned"}</td>
                      <td className="p-2">{getStatusBadge(line.status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Right Detail Pane */}
          <div className="space-y-4">
            {selectedLine ? (
              <Card className="border-border/40 bg-background/50">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center justify-between">
                    <span>{selectedLine.reference_designator} Details</span>
                    {getStatusBadge(selectedLine.status)}
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Design: {selectedLine.design_value} ({selectedLine.component_type})
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-xs">
                  <div>
                    <span className="text-muted-foreground">Required Specs:</span>
                    <div className="mt-1 bg-muted/30 p-2 rounded border border-border/20 space-y-1 font-mono text-[11px]">
                      <div>Nominal: {selectedLine.engineering_requirements?.nominal_value ?? selectedLine.design_value}</div>
                      {selectedLine.engineering_requirements?.max_tolerance_percent && (
                        <div>Tolerance: ±{selectedLine.engineering_requirements.max_tolerance_percent}%</div>
                      )}
                      {selectedLine.engineering_requirements?.min_voltage_rating_v && (
                        <div>Min Voltage: ≥{selectedLine.engineering_requirements.min_voltage_rating_v}V</div>
                      )}
                      {selectedLine.engineering_requirements?.min_power_rating_w && (
                        <div>Min Power: ≥{selectedLine.engineering_requirements.min_power_rating_w}W</div>
                      )}
                      {selectedLine.design_package && <div>Package: {selectedLine.design_package}</div>}
                    </div>
                  </div>

                  <div>
                    <span className="text-muted-foreground">Procurement Candidates ({selectedLine.candidates?.length || 0}):</span>
                    <div className="mt-1 space-y-1">
                      {selectedLine.candidates?.length ? (
                        selectedLine.candidates.map((cand) => (
                          <div
                            key={cand.id}
                            onClick={() => {
                              setSelectedCandidate(cand);
                              setActiveSubTab("candidates");
                            }}
                            className="p-2 rounded bg-muted/20 border border-border/20 hover:bg-muted/40 cursor-pointer flex items-center justify-between"
                          >
                            <div>
                              <div className="font-mono font-medium text-[11px]">{cand.mpn}</div>
                              <div className="text-muted-foreground text-[10px]">{cand.manufacturer}</div>
                            </div>
                            {getStatusBadge(cand.compatibility_status)}
                          </div>
                        ))
                      ) : (
                        <div className="text-muted-foreground italic text-[11px]">No candidate parts attached</div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <div className="text-xs text-muted-foreground italic p-4 text-center">Select a line to view details</div>
            )}
          </div>
        </div>
      )}

      {/* SUB-TAB 2: CANDIDATES */}
      {activeSubTab === "candidates" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {bom.lines?.flatMap((l) => l.candidates || []).map((cand) => (
              <Card key={cand.id} className="border-border/40 bg-background/50">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-sm font-mono">{cand.mpn}</CardTitle>
                      <CardDescription className="text-xs">{cand.manufacturer} | Pkg: {cand.package || "N/A"}</CardDescription>
                    </div>
                    <div className="flex gap-1">
                      {getStatusBadge(cand.compatibility_status)}
                      {getStatusBadge(cand.lifecycle_status)}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2 text-xs">
                  <div className="font-semibold text-muted-foreground text-[11px]">Compatibility Checks:</div>
                  <div className="space-y-1">
                    {cand.compatibility_evaluations?.map((ev, idx) => (
                      <div key={idx} className="flex items-center justify-between p-1 rounded bg-muted/20 font-mono text-[11px]">
                        <span>{ev.parameter}:</span>
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">{ev.message || ev.status}</span>
                          {ev.status === "SATISFIED" ? (
                            <Check className="h-3 w-3 text-emerald-500" />
                          ) : ev.status === "CONFLICT" || ev.status === "NOT_SATISFIED" ? (
                            <X className="h-3 w-3 text-rose-500" />
                          ) : (
                            <HelpCircle className="h-3 w-3 text-zinc-400" />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* SUB-TAB 3: MULTI-SOURCE SUPPLY */}
      {activeSubTab === "supply" && (
        <div className="space-y-4">
          <div className="rounded-md border border-border/40 overflow-hidden">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 border-b border-border/40 text-muted-foreground font-medium">
                <tr>
                  <th className="p-2">MPN</th>
                  <th className="p-2">Supplier</th>
                  <th className="p-2">Stock</th>
                  <th className="p-2">Unit Price</th>
                  <th className="p-2">Lead Time</th>
                  <th className="p-2">Observed At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {bom.lines?.flatMap((l) =>
                  (l.candidates || []).flatMap((c) =>
                    (c.supply_sources || []).map((s, idx) => (
                      <tr key={`${c.id}-${idx}`} className="hover:bg-muted/20">
                        <td className="p-2 font-mono">{c.mpn}</td>
                        <td className="p-2 font-medium">{s.supplier}</td>
                        <td className="p-2 font-mono">
                          {s.stock > 0 ? (
                            <span className="text-emerald-500">{s.stock.toLocaleString()}</span>
                          ) : (
                            <span className="text-rose-500">0</span>
                          )}
                        </td>
                        <td className="p-2 font-mono">
                          {s.unit_price != null ? `$${s.unit_price.toFixed(4)}` : "—"}
                        </td>
                        <td className="p-2">{c.lead_time_weeks ? `${c.lead_time_weeks} wks` : "N/A"}</td>
                        <td className="p-2 text-muted-foreground font-mono text-[10px]">{s.observed_at}</td>
                      </tr>
                    ))
                  )
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SUB-TAB 4: SUBSTITUTION PROPOSALS */}
      {activeSubTab === "substitutions" && (
        <div className="space-y-4">
          {bom.substitutions?.length ? (
            bom.substitutions.map((prop) => (
              <Card key={prop.id} className="border-border/40 bg-background/50">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-sm">
                        Propose {prop.proposed_mpn} ({prop.proposed_manufacturer})
                      </CardTitle>
                      <CardDescription className="text-xs">
                        Rationale: {prop.rationale}
                      </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{prop.status}</Badge>
                      {prop.status === "PROPOSED" && (
                        <Button
                          size="sm"
                          onClick={() => approveSubstitutionMutation.mutate(prop.id)}
                          disabled={approveSubstitutionMutation.isPending}
                        >
                          {approveSubstitutionMutation.isPending && (
                            <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                          )}
                          Approve (Human Gate)
                        </Button>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2 text-xs">
                  <div className="text-muted-foreground font-semibold">Side-by-Side Diff:</div>
                  <pre className="p-2 bg-muted/30 rounded border border-border/20 text-[10px] font-mono overflow-auto max-h-48">
                    {JSON.stringify(prop.diff_preview, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            ))
          ) : (
            <div className="text-sm text-muted-foreground italic text-center p-8">
              No substitution proposals created. Propose alternatives when lead times or availability conflicts arise.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
