"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Network,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  RefreshCw,
  Loader2,
  Fingerprint,
  Info,
  Filter,
  FileCheck2,
  Activity,
  Layers,
  Cpu,
  Boxes,
  ScrollText,
  Sliders,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { apiClient } from "@/lib/api";
import {
  CrossDomainFinding,
  CrossDomainValidationResponse,
  CrossDomainValidationSummary,
  CrossDomainStatus,
  CrossDomainSeverity,
} from "./types";

interface CrossDomainValidationTabProps {
  projectId: string;
  circuitId?: string | null;
}

export function CrossDomainValidationTab({ projectId, circuitId }: CrossDomainValidationTabProps) {
  const queryClient = useQueryClient();
  const [activeSubTab, setActiveSubTab] = useState<"findings" | "digest" | "rules">("findings");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [domainFilter, setDomainFilter] = useState<string>("ALL");
  const [selectedFinding, setSelectedFinding] = useState<CrossDomainFinding | null>(null);

  // 1. Fetch Latest Cross-Domain Validation Record
  const {
    data: validationData,
    isLoading: isRecordLoading,
    error: recordError,
    refetch: refetchLatest,
  } = useQuery<CrossDomainValidationResponse | null>({
    queryKey: ["cross-domain-latest", projectId],
    queryFn: async () => {
      try {
        const res = await apiClient.get(`/projects/${projectId}/cross-domain/latest`);
        return res.data?.data || null;
      } catch (err: any) {
        if (err.response?.status === 404) {
          return null;
        }
        throw err;
      }
    },
    enabled: !!projectId,
  });

  // 2. Run New Cross-Domain Validation Mutation
  const validateMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post(`/projects/${projectId}/cross-domain/validate`, {
        circuit_id: circuitId || undefined,
      });
      return res.data?.data as CrossDomainValidationResponse;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["cross-domain-latest", projectId], data);
      queryClient.invalidateQueries({ queryKey: ["cross-domain-records", projectId] });
    },
  });

  const summary = validationData?.summary;
  const findings = validationData?.findings || [];

  // Filtered Findings
  const filteredFindings = findings.filter((f) => {
    if (statusFilter !== "ALL" && f.status !== statusFilter) return false;
    if (domainFilter !== "ALL" && f.domain_a !== domainFilter && f.domain_b !== domainFilter) return false;
    return true;
  });

  const getStatusBadge = (status: CrossDomainStatus) => {
    switch (status) {
      case "PASS":
        return <Badge className="bg-emerald-950 text-emerald-400 border border-emerald-800 flex items-center gap-1 font-mono text-[10px]"><CheckCircle2 className="w-3 h-3" /> PASS</Badge>;
      case "FAIL":
        return <Badge className="bg-rose-950 text-rose-400 border border-rose-800 flex items-center gap-1 font-mono text-[10px]"><XCircle className="w-3 h-3" /> FAIL</Badge>;
      case "WARNING":
        return <Badge className="bg-amber-950 text-amber-400 border border-amber-800 flex items-center gap-1 font-mono text-[10px]"><AlertTriangle className="w-3 h-3" /> WARNING</Badge>;
      case "UNKNOWN":
        return <Badge className="bg-zinc-800 text-zinc-300 border border-zinc-700 flex items-center gap-1 font-mono text-[10px]"><HelpCircle className="w-3 h-3" /> UNKNOWN</Badge>;
      case "NOT_APPLICABLE":
        return <Badge className="bg-zinc-900 text-zinc-500 border border-zinc-800 font-mono text-[10px]">N/A</Badge>;
      default:
        return <Badge variant="outline" className="text-zinc-400 font-mono text-[10px]">{status}</Badge>;
    }
  };

  const getSeverityBadge = (severity: CrossDomainSeverity) => {
    switch (severity) {
      case "CRITICAL":
        return <Badge className="bg-red-950 text-red-300 border border-red-700 font-mono text-[10px]">CRITICAL</Badge>;
      case "HIGH":
        return <Badge className="bg-orange-950 text-orange-300 border border-orange-800 font-mono text-[10px]">HIGH</Badge>;
      case "MEDIUM":
        return <Badge className="bg-amber-950 text-amber-300 border border-amber-800 font-mono text-[10px]">MEDIUM</Badge>;
      case "LOW":
        return <Badge className="bg-zinc-800 text-zinc-300 border border-zinc-700 font-mono text-[10px]">LOW</Badge>;
      default:
        return <Badge variant="outline" className="text-zinc-400 font-mono text-[10px]">INFO</Badge>;
    }
  };

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Header and Epistemic Invariant Banner */}
      <div className="rounded-lg border border-cyan-900/60 bg-cyan-950/20 p-3 flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Network className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-cyan-300">
              Cross-Domain Validation & Verification
            </h2>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => validateMutation.mutate()}
            disabled={validateMutation.isPending}
            className="h-7 text-xs border-cyan-800 bg-cyan-950/60 hover:bg-cyan-900/60 text-cyan-300 flex items-center gap-1.5"
          >
            {validateMutation.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5" />
            )}
            Run Verification
          </Button>
        </div>
        <p className="text-[11px] text-zinc-400 leading-relaxed">
          Verifies physical, functional, and electrical consistency across Schematic, PCB, BOM, Simulation, Requirements, and DFM domains.
        </p>
        <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-cyan-950/80 text-[10px] text-zinc-400 font-mono">
          <span className="text-amber-400">UNKNOWN != PASS</span>
          <span>•</span>
          <span className="text-sky-400">CALCULATED != PHYSICALLY VERIFIED</span>
          <span>•</span>
          <span className="text-purple-400">HISTORICAL != CURRENT</span>
          <span>•</span>
          <span className="text-emerald-400">ZERO SYNTHETIC SCORING</span>
        </div>
      </div>

      {/* Summary KPI Cards (Strictly Categorical Counts - Zero Synthetic Scoring) */}
      {summary && (
        <div className="grid grid-cols-4 gap-2">
          <Card className="bg-zinc-900/40 border-zinc-800 p-2 text-center">
            <div className="text-[10px] font-mono text-zinc-400 uppercase">Evaluated</div>
            <div className="text-base font-bold font-mono text-zinc-200 mt-0.5">{summary.total_findings}</div>
          </Card>
          <Card className="bg-emerald-950/20 border-emerald-900/40 p-2 text-center">
            <div className="text-[10px] font-mono text-emerald-400 uppercase">Pass</div>
            <div className="text-base font-bold font-mono text-emerald-300 mt-0.5">{summary.pass_count}</div>
          </Card>
          <Card className="bg-rose-950/20 border-rose-900/40 p-2 text-center">
            <div className="text-[10px] font-mono text-rose-400 uppercase">Critical/Fail</div>
            <div className="text-base font-bold font-mono text-rose-300 mt-0.5">{summary.fail_count}</div>
          </Card>
          <Card className="bg-zinc-900/40 border-zinc-800 p-2 text-center">
            <div className="text-[10px] font-mono text-zinc-400 uppercase">Unknown/Warn</div>
            <div className="text-base font-bold font-mono text-amber-300 mt-0.5">
              {summary.unknown_count + summary.warning_count}
            </div>
          </Card>
        </div>
      )}

      {/* Staleness Warning */}
      {validationData?.is_stale && (
        <div className="rounded-lg border border-amber-800/80 bg-amber-950/40 p-2.5 flex items-start gap-2 text-xs text-amber-200">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <span className="font-semibold block text-[11px] uppercase tracking-wider text-amber-300">
              STALE VERIFICATION RECORD
            </span>
            <p className="text-[11px] text-amber-200/90 leading-relaxed">
              Design artifacts have been modified since this evaluation was run. Re-run verification to update cross-domain consistency.
              {validationData.staleness_reasons && validationData.staleness_reasons.length > 0 && (
                <span className="block text-[10px] text-amber-300/80 mt-1 font-mono">
                  Reasons: {validationData.staleness_reasons.join("; ")}
                </span>
              )}
            </p>
          </div>
        </div>
      )}

      {/* Navigation Subtabs */}
      <div className="flex items-center border-b border-zinc-800 pb-1 gap-1 shrink-0">
        <button
          onClick={() => setActiveSubTab("findings")}
          className={`px-3 py-1 text-xs rounded transition-colors ${
            activeSubTab === "findings"
              ? "bg-zinc-800 text-cyan-400 font-medium"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Consistency Findings ({findings.length})
        </button>
        <button
          onClick={() => setActiveSubTab("digest")}
          className={`px-3 py-1 text-xs rounded transition-colors flex items-center gap-1.5 ${
            activeSubTab === "digest"
              ? "bg-zinc-800 text-cyan-400 font-medium"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Fingerprint className="w-3.5 h-3.5" />
          Provenance Digest
        </button>
        <button
          onClick={() => setActiveSubTab("rules")}
          className={`px-3 py-1 text-xs rounded transition-colors flex items-center gap-1.5 ${
            activeSubTab === "rules"
              ? "bg-zinc-800 text-cyan-400 font-medium"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <ScrollText className="w-3.5 h-3.5" />
          Cross-Domain Rules
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto space-y-3">
        {isRecordLoading ? (
          <div className="flex flex-col items-center justify-center p-8 text-zinc-500 gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-cyan-500" />
            <p className="text-xs">Loading cross-domain verification state...</p>
          </div>
        ) : !validationData ? (
          <Card className="bg-zinc-900/30 border-zinc-800 p-6 text-center">
            <Network className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
            <h3 className="text-xs font-semibold text-zinc-300">No Validation Executed Yet</h3>
            <p className="text-[11px] text-zinc-500 mt-1 max-w-sm mx-auto">
              Run verification to evaluate consistency across Schematic, PCB layout, BOM lines, thermal limits, simulation state, and manufacturing rules.
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => validateMutation.mutate()}
              disabled={validateMutation.isPending}
              className="mt-4 h-7 text-xs border-cyan-800 bg-cyan-950/60 text-cyan-300 hover:bg-cyan-900/60"
            >
              Initiate Cross-Domain Verification
            </Button>
          </Card>
        ) : activeSubTab === "findings" ? (
          <div className="space-y-3">
            {/* Filter Bar */}
            <div className="flex items-center gap-2 text-xs">
              <span className="text-zinc-500 text-[11px] flex items-center gap-1">
                <Filter className="w-3 h-3" /> Status:
              </span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                aria-label="Filter findings by status"
                className="bg-zinc-900 border border-zinc-800 rounded px-2 py-0.5 text-xs text-zinc-300"
              >
                <option value="ALL">All Statuses</option>
                <option value="FAIL">FAIL</option>
                <option value="WARNING">WARNING</option>
                <option value="UNKNOWN">UNKNOWN</option>
                <option value="PASS">PASS</option>
              </select>

              <span className="text-zinc-500 text-[11px] ml-2">Domain:</span>
              <select
                value={domainFilter}
                onChange={(e) => setDomainFilter(e.target.value)}
                aria-label="Filter findings by domain"
                className="bg-zinc-900 border border-zinc-800 rounded px-2 py-0.5 text-xs text-zinc-300"
              >
                <option value="ALL">All Domains</option>
                <option value="SCHEMATIC">Schematic</option>
                <option value="PCB">PCB</option>
                <option value="BOM">BOM</option>
                <option value="SIMULATION">Simulation</option>
                <option value="POWER_THERMAL">Power & Thermal</option>
                <option value="REQUIREMENTS">Requirements</option>
                <option value="VERIFICATION">Verification</option>
                <option value="DFM">DFM</option>
              </select>
            </div>

            {/* Findings List */}
            <div className="space-y-2">
              {filteredFindings.length === 0 ? (
                <p className="text-xs text-zinc-500 text-center py-4">No findings match the selected filters.</p>
              ) : (
                filteredFindings.map((finding) => (
                  <Card
                    key={finding.finding_id}
                    className={`bg-zinc-900/50 border transition-colors cursor-pointer ${
                      selectedFinding?.finding_id === finding.finding_id
                        ? "border-cyan-500"
                        : "border-zinc-800 hover:border-zinc-700"
                    }`}
                    onClick={() => setSelectedFinding(finding)}
                  >
                    <CardContent className="p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-[11px] font-bold text-zinc-300">
                              {finding.rule_id}
                            </span>
                            <span className="text-[10px] font-mono text-zinc-500">
                              [{finding.domain_a} ↔ {finding.domain_b}]
                            </span>
                            {getStatusBadge(finding.status)}
                            {getSeverityBadge(finding.severity)}
                          </div>
                          <p className="text-xs text-zinc-200 mt-1 font-medium">
                            {finding.engineering_claim}
                          </p>
                          <p className="text-[11px] text-zinc-400 leading-normal">
                            {finding.explanation}
                          </p>
                        </div>
                      </div>

                      {/* Quantitative Values & Source Classification */}
                      <div className="mt-2 pt-2 border-t border-zinc-800/80 flex items-center justify-between text-[10px] font-mono text-zinc-500">
                        <span>Classification: <span className="text-zinc-400">{finding.source_classification}</span></span>
                        {finding.margin !== undefined && finding.margin !== null && (
                          <span>Margin: <span className={finding.margin < 0 ? "text-rose-400" : "text-emerald-400"}>{finding.margin}</span></span>
                        )}
                        {finding.affected_entity_ids.length > 0 && (
                          <span>Entities: <span className="text-zinc-400">{finding.affected_entity_ids.join(", ")}</span></span>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          </div>
        ) : activeSubTab === "digest" ? (
          <div className="space-y-3">
            <Card className="bg-zinc-900/40 border-zinc-800 p-4 space-y-3">
              <div className="flex items-center gap-2 text-cyan-400">
                <Fingerprint className="w-4 h-4" />
                <h4 className="text-xs font-semibold uppercase tracking-wider">Provenance & Integrity Digest</h4>
              </div>
              <div className="rounded bg-zinc-950 p-3 font-mono text-xs text-zinc-300 border border-zinc-800 break-all select-all">
                {validationData.snapshot_digest || "NO_DIGEST_RECORDED"}
              </div>
              <div className="rounded border border-amber-900/60 bg-amber-950/20 p-2.5 text-[11px] text-amber-300/90 leading-relaxed">
                <span className="font-semibold block mb-0.5">EPISTEMIC BOUNDARY NOTICE:</span>
                This SHA-256 digest represents a canonical serialization of multi-domain state at validation time (PROVENANCE_AND_INTEGRITY_DIGEST). It is <span className="underline font-semibold">NOT</span> a digital signature or manufacturer guarantee.
              </div>
              <div className="text-[11px] text-zinc-400 space-y-1 pt-1 font-mono">
                <div>Record ID: {validationData.id}</div>
                <div>Status: {validationData.status}</div>
                <div>Evaluated At: {new Date(validationData.created_at).toLocaleString()}</div>
                <div>Domains Evaluated: {validationData.summary.domains_evaluated.join(", ")}</div>
              </div>
            </Card>
          </div>
        ) : (
          <div className="space-y-3">
            <Card className="bg-zinc-900/40 border-zinc-800 p-4 space-y-2">
              <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                System Rules (X001 – X020)
              </h4>
              <p className="text-[11px] text-zinc-400">
                Rules enforced across domains without AI decision authority:
              </p>
              <div className="grid grid-cols-1 gap-2 pt-2">
                {[
                  { id: "X001", pair: "Schematic ↔ PCB", desc: "Netlist connectivity and net-pin topology agreement" },
                  { id: "X002", pair: "Schematic ↔ PCB", desc: "Component footprint placement completeness" },
                  { id: "X003", pair: "Schematic ↔ BOM", desc: "RefDes and design value synchronisation" },
                  { id: "X004", pair: "BOM ↔ PCB", desc: "Footprint name and physical package alignment" },
                  { id: "X005", pair: "BOM ↔ PCB", desc: "Component pin count to footprint pad count match" },
                  { id: "X006", pair: "Schematic ↔ Datasheet", desc: "Continuous operating limits compliance" },
                  { id: "X007", pair: "Schematic ↔ Datasheet", desc: "Absolute maximum ratings violation check" },
                  { id: "X008", pair: "Schematic ↔ Power", desc: "Power rail budget and current capacity margin" },
                  { id: "X009", pair: "Schematic ↔ Thermal", desc: "Component thermal junction dissipation limit" },
                  { id: "X010", pair: "PCB ↔ Thermal", desc: "High-power package thermal via presence" },
                  { id: "X011", pair: "Schematic ↔ SPICE", desc: "SPICE simulation currency against active revision" },
                  { id: "X012", pair: "Simulation ↔ Engineering", desc: "SPICE convergence and numerical stability" },
                  { id: "X013", pair: "Requirements ↔ Verification", desc: "Engineering requirement evidence substantiation" },
                  { id: "X014", pair: "Schematic ↔ DFM", desc: "Voltage isolation and copper spacing clearance" },
                  { id: "X015", pair: "PCB ↔ DFM", desc: "DFM analysis currency against active board revision" },
                  { id: "X016", pair: "Verification ↔ Design", desc: "Verification evidence revision alignment" },
                  { id: "X017", pair: "Historical ↔ Current", desc: "Historical verification does not verify current revision" },
                  { id: "X018", pair: "Source ↔ Currency", desc: "Datasheet/specification revision currency" },
                  { id: "X019", pair: "Component ↔ Procurement", desc: "Component identity vs procurement candidate MPN" },
                  { id: "X020", pair: "Multi-Domain", desc: "7-Domain cross-system verification completeness" },
                ].map((rule) => (
                  <div key={rule.id} className="p-2 rounded bg-zinc-950/60 border border-zinc-800/80 text-[11px]">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-cyan-400">{rule.id}</span>
                      <span className="text-zinc-500 font-mono text-[10px]">[{rule.pair}]</span>
                    </div>
                    <div className="text-zinc-300 mt-0.5">{rule.desc}</div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
