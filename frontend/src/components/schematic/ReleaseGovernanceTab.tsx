"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  RefreshCw,
  Loader2,
  Fingerprint,
  FileCheck2,
  Clock,
  Layers,
  Lock,
  ExternalLink,
  ChevronRight,
  ChevronDown,
  Tag,
  FileText,
  UserCheck,
  AlertCircle,
  Activity,
  History,
  Shield,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { apiClient } from "@/lib/api";
import {
  ReleaseEvaluationResponse,
  ReleaseBaselineResponse,
  ReleaseGateDetail,
  OverallReadinessState,
  ReleaseGateStatus,
} from "./types";

interface ReleaseGovernanceTabProps {
  projectId: string;
  circuitId?: string | null;
}

const READINESS_CONFIG: Record<
  OverallReadinessState,
  { label: string; bg: string; text: string; border: string; icon: any; desc: string }
> = {
  READY_FOR_RELEASE: {
    label: "READY FOR RELEASE",
    bg: "bg-emerald-950/60",
    text: "text-emerald-400",
    border: "border-emerald-800",
    icon: CheckCircle2,
    desc: "All applicable engineering release gates PASS. Human authorization unlocked.",
  },
  NOT_READY: {
    label: "NOT READY",
    bg: "bg-amber-950/60",
    text: "text-amber-400",
    border: "border-amber-800",
    icon: AlertTriangle,
    desc: "One or more gates failed or require verified physical evidence before release.",
  },
  BLOCKED: {
    label: "BLOCKED",
    bg: "bg-red-950/60",
    text: "text-red-400",
    border: "border-red-800",
    icon: XCircle,
    desc: "Critical failures or audit chain discrepancy detected. Release strictly forbidden.",
  },
  STALE: {
    label: "STALE",
    bg: "bg-zinc-800/80",
    text: "text-zinc-300",
    border: "border-zinc-700",
    icon: Clock,
    desc: "Authoritative design or audit ledger mutated post-evaluation. Re-run required.",
  },
};

const GATE_STATUS_BADGES: Record<
  ReleaseGateStatus,
  { label: string; bg: string; text: string; border: string; icon: any }
> = {
  PASS: {
    label: "PASS",
    bg: "bg-emerald-950/50",
    text: "text-emerald-400",
    border: "border-emerald-800/80",
    icon: CheckCircle2,
  },
  FAIL: {
    label: "FAIL",
    bg: "bg-red-950/50",
    text: "text-red-400",
    border: "border-red-800/80",
    icon: XCircle,
  },
  BLOCKED: {
    label: "BLOCKED",
    bg: "bg-red-950/60",
    text: "text-red-400",
    border: "border-red-900",
    icon: AlertCircle,
  },
  UNKNOWN: {
    label: "UNKNOWN",
    bg: "bg-purple-950/50",
    text: "text-purple-400",
    border: "border-purple-800/80",
    icon: HelpCircle,
  },
  STALE: {
    label: "STALE",
    bg: "bg-amber-950/50",
    text: "text-amber-400",
    border: "border-amber-800/80",
    icon: Clock,
  },
  NOT_APPLICABLE: {
    label: "N/A",
    bg: "bg-zinc-900/60",
    text: "text-zinc-400",
    border: "border-zinc-800",
    icon: FileText,
  },
};

export function ReleaseGovernanceTab({ projectId, circuitId }: ReleaseGovernanceTabProps) {
  const queryClient = useQueryClient();
  const [activeSubTab, setActiveSubTab] = useState<"gates" | "baselines" | "audit">("gates");
  const [selectedGateId, setSelectedGateId] = useState<string | null>(null);

  // Authorize Baseline Dialog State
  const [isAuthorizeModalOpen, setIsAuthorizeModalOpen] = useState(false);
  const [releaseTag, setReleaseTag] = useState("");
  const [releaseRationale, setReleaseRationale] = useState("");
  const [authorizationError, setAuthorizationError] = useState<string | null>(null);

  // 1. Fetch Latest Release Readiness Evaluation
  const {
    data: evaluation,
    isLoading: isEvalLoading,
    refetch: refetchEval,
  } = useQuery<ReleaseEvaluationResponse | null>({
    queryKey: ["release-evaluation-latest", projectId],
    queryFn: async () => {
      try {
        const res = await apiClient.get(`/projects/${projectId}/release/evaluations/latest`);
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

  // 2. Fetch Historical Frozen Release Baselines
  const {
    data: baselines = [],
    isLoading: isBaselinesLoading,
    refetch: refetchBaselines,
  } = useQuery<ReleaseBaselineResponse[]>({
    queryKey: ["release-baselines", projectId],
    queryFn: async () => {
      const res = await apiClient.get(`/projects/${projectId}/release/baselines`);
      return res.data?.data || [];
    },
    enabled: !!projectId,
  });

  // 3. Mutation: Run Evaluation
  const evaluateMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post(`/projects/${projectId}/release/evaluate`, {
        circuit_id: circuitId || undefined,
      });
      return res.data?.data as ReleaseEvaluationResponse;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["release-evaluation-latest", projectId], data);
      queryClient.invalidateQueries({ queryKey: ["release-evaluation-latest", projectId] });
    },
  });

  // 4. Mutation: Authorize Release Baseline
  const authorizeMutation = useMutation({
    mutationFn: async () => {
      if (!evaluation) throw new Error("No evaluation available to authorize.");
      const res = await apiClient.post(`/projects/${projectId}/release/baselines`, {
        evaluation_id: evaluation.id,
        release_tag: releaseTag.trim(),
        release_rationale: releaseRationale.trim(),
        exceptions_approved: [],
      });
      return res.data?.data as ReleaseBaselineResponse;
    },
    onSuccess: () => {
      setIsAuthorizeModalOpen(false);
      setReleaseTag("");
      setReleaseRationale("");
      setAuthorizationError(null);
      queryClient.invalidateQueries({ queryKey: ["release-baselines", projectId] });
      queryClient.invalidateQueries({ queryKey: ["release-evaluation-latest", projectId] });
      setActiveSubTab("baselines");
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail || err.message || "Release authorization failed.";
      setAuthorizationError(detail);
    },
  });

  const readinessState: OverallReadinessState = evaluation?.is_stale
    ? "STALE"
    : evaluation?.overall_readiness || "NOT_READY";
  const readinessMeta = READINESS_CONFIG[readinessState];
  const ReadinessIcon = readinessMeta.icon;

  const gatesList: ReleaseGateDetail[] = evaluation?.gate_results
    ? Object.values(evaluation.gate_results).sort((a, b) => a.gate_id.localeCompare(b.gate_id))
    : [];

  const selectedGate = selectedGateId && evaluation?.gate_results
    ? evaluation.gate_results[selectedGateId]
    : gatesList[0] || null;

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* 1. Header Overview & Primary Call to Action */}
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-lg p-4 backdrop-blur shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-emerald-400" />
              <h2 className="text-base font-semibold text-zinc-100 tracking-tight">
                Engineering Release Governance
              </h2>
              <Badge variant="outline" className="text-[10px] font-mono text-zinc-400 border-zinc-700">
                WAVE 10D
              </Badge>
              <Badge variant="outline" className="text-[10px] font-mono text-zinc-500 border-zinc-800">
                AI AUTHORITY: NONE
              </Badge>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed max-w-2xl">
              Deterministic verification of release gates RG-01 through RG-09, cryptographic
              audit-ledger anchor verification, and human-authorized frozen baselines.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2.5">
            <Button
              size="sm"
              variant="outline"
              onClick={() => evaluateMutation.mutate()}
              disabled={evaluateMutation.isPending || isEvalLoading}
              className="text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border-zinc-700"
            >
              {evaluateMutation.isPending ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  Evaluating...
                </>
              ) : (
                <>
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5 text-zinc-400" />
                  Evaluate Readiness
                </>
              )}
            </Button>

            <Button
              size="sm"
              onClick={() => {
                setAuthorizationError(null);
                setIsAuthorizeModalOpen(true);
              }}
              disabled={
                !evaluation ||
                readinessState !== "READY_FOR_RELEASE" ||
                evaluation.is_stale ||
                evaluateMutation.isPending
              }
              className="text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-medium shadow-sm transition-all disabled:opacity-50"
            >
              <Lock className="w-3.5 h-3.5 mr-1.5" />
              Authorize Release Baseline
            </Button>
          </div>
        </div>

        {/* Overall Readiness Banner */}
        {evaluation ? (
          <div
            className={`mt-4 p-3.5 rounded-md border flex flex-col md:flex-row md:items-center justify-between gap-3 ${readinessMeta.bg} ${readinessMeta.border}`}
          >
            <div className="flex items-center gap-3">
              <ReadinessIcon className={`w-5 h-5 shrink-0 ${readinessMeta.text}`} />
              <div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold uppercase tracking-wider font-mono ${readinessMeta.text}`}>
                    {readinessMeta.label}
                  </span>
                  {evaluation.is_stale && (
                    <Badge variant="outline" className="text-[10px] font-mono text-amber-400 border-amber-800 bg-amber-950/60">
                      STALE
                    </Badge>
                  )}
                  <span className="text-[11px] text-zinc-400 font-mono">
                    Rev: v{evaluation.project_revision} • Ver: {evaluation.evaluator_version}
                  </span>
                </div>
                <p className="text-xs text-zinc-300 mt-0.5">{readinessMeta.desc}</p>
              </div>
            </div>

            <div className="flex items-center gap-3 shrink-0 text-[11px] font-mono text-zinc-400">
              <div className="flex items-center gap-1.5 bg-zinc-900/60 px-2.5 py-1 rounded border border-zinc-800">
                <Fingerprint className="w-3.5 h-3.5 text-zinc-400" />
                <span>{evaluation.state_fingerprint.slice(0, 12)}…</span>
              </div>
              <div className="flex items-center gap-1.5 bg-zinc-900/60 px-2.5 py-1 rounded border border-zinc-800">
                <Clock className="w-3.5 h-3.5 text-zinc-400" />
                <span>{new Date(evaluation.evaluated_at).toLocaleTimeString()}</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="mt-4 p-4 rounded-md border border-zinc-800 bg-zinc-950/40 text-center">
            <p className="text-xs text-zinc-400">
              No release evaluation recorded for this project revision. Click "Evaluate Readiness" to initiate RG-01 through RG-09 verification.
            </p>
          </div>
        )}
      </div>

      {/* 2. Sub-tab Navigation */}
      <div className="flex items-center gap-2 border-b border-zinc-800 pb-2">
        <button
          onClick={() => setActiveSubTab("gates")}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5 ${
            activeSubTab === "gates"
              ? "bg-zinc-800 text-zinc-100 font-semibold shadow-sm"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Layers className="w-3.5 h-3.5 text-sky-400" />
          Release Gates (RG-01–09)
          {gatesList.length > 0 && (
            <span className="text-[10px] px-1.5 py-0.2 bg-zinc-700 rounded-full font-mono">
              {gatesList.filter((g) => g.status === "PASS").length}/{gatesList.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveSubTab("baselines")}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5 ${
            activeSubTab === "baselines"
              ? "bg-zinc-800 text-zinc-100 font-semibold shadow-sm"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <History className="w-3.5 h-3.5 text-emerald-400" />
          Frozen Baselines
          <span className="text-[10px] px-1.5 py-0.2 bg-zinc-700 rounded-full font-mono">
            {baselines.length}
          </span>
        </button>

        <button
          onClick={() => setActiveSubTab("audit")}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5 ${
            activeSubTab === "audit"
              ? "bg-zinc-800 text-zinc-100 font-semibold shadow-sm"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5 text-teal-400" />
          Audit Ledger Integrity
          {evaluation?.audit_chain_verified ? (
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
          ) : (
            <span className="w-2 h-2 rounded-full bg-red-400" />
          )}
        </button>
      </div>

      {/* 3. Sub-tab Content Panels */}

      {/* TAB A: Release Gates (RG-01 to RG-09) */}
      {activeSubTab === "gates" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 overflow-hidden">
          {/* Left Column: Gates List */}
          <div className="lg:col-span-5 space-y-2 overflow-y-auto max-h-[550px] pr-1">
            {gatesList.length === 0 ? (
              <div className="p-8 text-center border border-zinc-800 rounded-lg bg-zinc-900/40">
                <Activity className="w-8 h-8 text-zinc-600 mx-auto mb-2 animate-pulse" />
                <p className="text-xs text-zinc-400">Click "Evaluate Readiness" to generate gate assessments.</p>
              </div>
            ) : (
              gatesList.map((gate) => {
                const statusMeta = GATE_STATUS_BADGES[gate.status];
                const StatusIcon = statusMeta.icon;
                const isSelected = selectedGate?.gate_id === gate.gate_id;

                return (
                  <div
                    key={gate.gate_id}
                    onClick={() => setSelectedGateId(gate.gate_id)}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      isSelected
                        ? "bg-zinc-800/90 border-sky-600/80 shadow-md"
                        : "bg-zinc-900/60 border-zinc-800/80 hover:bg-zinc-850 hover:border-zinc-700"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold font-mono text-zinc-200">
                          {gate.gate_id}
                        </span>
                        <span className="text-xs font-medium text-zinc-300 truncate max-w-[180px]">
                          {gate.name}
                        </span>
                      </div>
                      <Badge
                        variant="outline"
                        className={`text-[10px] font-mono flex items-center gap-1 ${statusMeta.bg} ${statusMeta.text} ${statusMeta.border}`}
                      >
                        <StatusIcon className="w-3 h-3" />
                        {statusMeta.label}
                      </Badge>
                    </div>

                    <div className="mt-1.5 flex items-center justify-between text-[11px] text-zinc-500 font-mono">
                      <span>Scope: {gate.applicable_scope}</span>
                      {gate.failure_reasons.length > 0 && (
                        <span className="text-red-400 font-sans">
                          {gate.failure_reasons.length} blocking defect{gate.failure_reasons.length > 1 ? "s" : ""}
                        </span>
                      )}
                      {gate.missing_evidence.length > 0 && (
                        <span className="text-amber-400 font-sans">
                          {gate.missing_evidence.length} missing evidence
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Right Column: Detailed Gate Inspector */}
          <div className="lg:col-span-7 bg-zinc-900/70 border border-zinc-800 rounded-lg p-4 overflow-y-auto max-h-[550px]">
            {selectedGate ? (
              <div className="space-y-4">
                <div className="flex items-start justify-between border-b border-zinc-800 pb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold font-mono text-sky-400">
                        {selectedGate.gate_id}
                      </span>
                      <h3 className="text-sm font-semibold text-zinc-100">{selectedGate.name}</h3>
                    </div>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      Scope: <span className="font-mono text-zinc-300">{selectedGate.applicable_scope}</span> • Version:{" "}
                      <span className="font-mono text-zinc-300">{selectedGate.definition_version}</span>
                    </p>
                  </div>
                  <Badge
                    variant="outline"
                    className={`text-xs font-mono px-2 py-0.5 ${
                      GATE_STATUS_BADGES[selectedGate.status].bg
                    } ${GATE_STATUS_BADGES[selectedGate.status].text} ${
                      GATE_STATUS_BADGES[selectedGate.status].border
                    }`}
                  >
                    {selectedGate.status}
                  </Badge>
                </div>

                {/* Failure Reasons */}
                {selectedGate.failure_reasons.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-red-400 flex items-center gap-1.5">
                      <XCircle className="w-3.5 h-3.5" />
                      Failing Conditions & Blocking Reasons
                    </h4>
                    <div className="space-y-1.5">
                      {selectedGate.failure_reasons.map((reason, idx) => (
                        <div
                          key={idx}
                          className="p-2.5 rounded bg-red-950/40 border border-red-900/60 text-xs text-red-300 font-mono"
                        >
                          {reason}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Missing Evidence */}
                {selectedGate.missing_evidence.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-amber-400 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      Required Missing Evidence Items
                    </h4>
                    <div className="space-y-1.5">
                      {selectedGate.missing_evidence.map((item, idx) => (
                        <div
                          key={idx}
                          className="p-2.5 rounded bg-amber-950/40 border border-amber-900/60 text-xs text-amber-300 font-mono"
                        >
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Stale Reasons */}
                {selectedGate.stale_reasons.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-zinc-400 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5" />
                      Staleness Disqualifications
                    </h4>
                    <div className="space-y-1.5">
                      {selectedGate.stale_reasons.map((item, idx) => (
                        <div
                          key={idx}
                          className="p-2.5 rounded bg-zinc-800/60 border border-zinc-700/60 text-xs text-zinc-300 font-mono"
                        >
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Authoritative Sources Evaluated */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
                    <FileCheck2 className="w-3.5 h-3.5 text-sky-400" />
                    Authoritative Sources
                  </h4>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedGate.authoritative_sources.map((src, idx) => (
                      <span
                        key={idx}
                        className="text-[11px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700"
                      >
                        {src}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Evidence Identifiers */}
                {selectedGate.evidence_identifiers.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
                      <Fingerprint className="w-3.5 h-3.5 text-purple-400" />
                      Cryptographic / Entity Identifiers
                    </h4>
                    <div className="bg-zinc-950 p-3 rounded border border-zinc-800 font-mono text-[11px] text-zinc-400 overflow-x-auto">
                      <pre>{JSON.stringify(selectedGate.evidence_identifiers, null, 2)}</pre>
                    </div>
                  </div>
                )}

                {/* Waiver Status */}
                {selectedGate.waived && (
                  <div className="p-3 rounded bg-blue-950/40 border border-blue-900/60 space-y-1">
                    <div className="flex items-center gap-2 text-xs font-semibold text-blue-300">
                      <UserCheck className="w-3.5 h-3.5" />
                      Waived by Human Engineer ({selectedGate.waived_by || "Authorized Engineer"})
                    </div>
                    <p className="text-xs text-blue-400">{selectedGate.waiver_rationale}</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-zinc-500">
                Select a release gate on the left to inspect its deterministic evidence and failure conditions.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB B: Frozen Baselines History */}
      {activeSubTab === "baselines" && (
        <div className="space-y-3 flex-1 overflow-y-auto pr-1">
          {baselines.length === 0 ? (
            <div className="p-12 text-center border border-zinc-800 rounded-lg bg-zinc-900/40 space-y-3">
              <Lock className="w-8 h-8 text-zinc-600 mx-auto" />
              <div className="space-y-1">
                <h4 className="text-sm font-semibold text-zinc-300">No Frozen Baselines</h4>
                <p className="text-xs text-zinc-500 max-w-md mx-auto">
                  When all release gates satisfy rigorous engineering criteria, an authorized human
                  engineer can sign off and create an immutable frozen baseline snapshot.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {baselines.map((b) => (
                <div
                  key={b.id}
                  className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-4 space-y-3 hover:border-zinc-700 transition-colors"
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-zinc-800 pb-2.5">
                    <div className="flex items-center gap-2.5">
                      <Tag className="w-4 h-4 text-emerald-400" />
                      <span className="text-sm font-bold font-mono text-zinc-100">{b.release_tag}</span>
                      <Badge variant="outline" className="text-[10px] font-mono text-zinc-400 border-zinc-700">
                        Rev: v{b.project_revision}
                      </Badge>
                      <Badge variant="outline" className="text-[10px] font-mono text-emerald-400 border-emerald-800 bg-emerald-950/40">
                        FROZEN IMMUTABLE
                      </Badge>
                    </div>

                    <div className="flex items-center gap-3 text-xs font-mono text-zinc-400">
                      <span>Authorized by: <strong className="text-zinc-200">{b.authorized_by_role}</strong></span>
                      <span>•</span>
                      <span>{new Date(b.authorized_at).toLocaleString()}</span>
                    </div>
                  </div>

                  {/* Rationale */}
                  <div className="text-xs text-zinc-300 bg-zinc-950/60 p-2.5 rounded border border-zinc-800/80">
                    <strong className="text-zinc-400">Sign-off Rationale: </strong>
                    {b.release_rationale}
                  </div>

                  {/* Cryptographic Digests */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] font-mono text-zinc-400">
                    <div className="p-2 rounded bg-zinc-950 border border-zinc-850 flex items-center justify-between">
                      <span className="text-zinc-500">Manifest Digest:</span>
                      <span className="text-zinc-300">{b.canonical_snapshot_digest.slice(0, 16)}…</span>
                    </div>
                    <div className="p-2 rounded bg-zinc-950 border border-zinc-850 flex items-center justify-between">
                      <span className="text-zinc-500">Audit Chain Head:</span>
                      <span className="text-zinc-300">{b.audit_chain_head_hash.slice(0, 16)}… (seq #{b.audit_chain_sequence})</span>
                    </div>
                  </div>

                  {/* Domain Sub-entity Snapshots */}
                  <div className="flex flex-wrap gap-2 text-[10px] font-mono text-zinc-400">
                    {b.circuit_digest && (
                      <span className="bg-zinc-800 px-2 py-0.5 rounded border border-zinc-700">
                        Circuit: v{b.circuit_version} ({b.circuit_digest.slice(0, 8)})
                      </span>
                    )}
                    {b.board_digest && (
                      <span className="bg-zinc-800 px-2 py-0.5 rounded border border-zinc-700">
                        PCB Board: v{b.board_version} ({b.board_digest.slice(0, 8)})
                      </span>
                    )}
                    {b.bom_digest && (
                      <span className="bg-zinc-800 px-2 py-0.5 rounded border border-zinc-700">
                        BOM: v{b.bom_version} ({b.bom_digest.slice(0, 8)})
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB C: Audit Ledger Integrity */}
      {activeSubTab === "audit" && (
        <div className="space-y-4 flex-1 overflow-y-auto pr-1">
          <Card className="bg-zinc-900/70 border-zinc-800">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    Cryptographic Hash Chain Verification
                  </CardTitle>
                  <CardDescription className="text-xs text-zinc-400 mt-1">
                    SHA-256 tamper-evident backlink chain securing all engineering mutations, DRC evaluations, and release events.
                  </CardDescription>
                </div>
                <Badge
                  variant="outline"
                  className={`text-xs font-mono ${
                    evaluation?.audit_chain_verified
                      ? "text-emerald-400 border-emerald-800 bg-emerald-950/60"
                      : "text-red-400 border-red-800 bg-red-950/60"
                  }`}
                >
                  {evaluation?.audit_chain_verified ? "VERIFIED VALID" : "TAMPER DETECTED"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono">
                <div className="p-3 rounded bg-zinc-950 border border-zinc-800 space-y-1">
                  <span className="text-zinc-500">Chain Head Hash</span>
                  <p className="text-zinc-200 truncate">{evaluation?.audit_chain_head_hash || "GENESIS"}</p>
                </div>
                <div className="p-3 rounded bg-zinc-950 border border-zinc-800 space-y-1">
                  <span className="text-zinc-500">Latest Event Sequence</span>
                  <p className="text-zinc-200">#{evaluation?.audit_chain_sequence ?? 0}</p>
                </div>
                <div className="p-3 rounded bg-zinc-950 border border-zinc-800 space-y-1">
                  <span className="text-zinc-500">External Anchor Checked</span>
                  <p className="text-zinc-200">{evaluation?.audit_chain_trusted_anchor_checked ? "YES" : "LOCAL CHAIN ONLY"}</p>
                </div>
              </div>

              <div className="p-3 rounded bg-zinc-950/80 border border-zinc-800 text-xs text-zinc-400 space-y-2">
                <h5 className="font-semibold text-zinc-300">Release Invariant Enforcement:</h5>
                <ul className="list-disc list-inside space-y-1 text-zinc-400 font-sans">
                  <li>Any discontinuity or broken hash backlink immediately sets overall readiness to <code className="font-mono text-red-400">BLOCKED</code>.</li>
                  <li>Autonomous mutation, automated release approval, and AI sign-offs are strictly rejected at the API boundary.</li>
                  <li>RFC 3161 external timestamp anchors bind immutable checkpoints independently verified against trusted TSA certificate chains.</li>
                  <li>Independent WORM retention is monitored and reported separately from local cryptographic verification.</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* 4. Human Release Authorization Modal Dialog */}
      {isAuthorizeModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2">
                <Lock className="w-5 h-5 text-emerald-400" />
                <h3 className="text-base font-semibold text-zinc-100">
                  Authorize Engineering Release Baseline
                </h3>
              </div>
              <button
                onClick={() => setIsAuthorizeModalOpen(false)}
                className="text-zinc-400 hover:text-zinc-200 text-sm"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-zinc-400 leading-relaxed">
              This action creates an immutable, frozen engineering baseline linked to the authoritative
              audit ledger. You must be an authorized human engineer. AI actors cannot authorize releases.
            </p>

            {authorizationError && (
              <div className="p-3 rounded bg-red-950/60 border border-red-800 text-xs text-red-300 font-mono">
                {authorizationError}
              </div>
            )}

            <div className="space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-medium text-zinc-300">
                  Release Tag <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. REL-2026.1-A or v1.0.0-PROD"
                  value={releaseTag}
                  onChange={(e) => setReleaseTag(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-zinc-100 font-mono text-xs focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-medium text-zinc-300">
                  Sign-off Justification & Engineering Rationale <span className="text-red-400">*</span>
                </label>
                <textarea
                  rows={3}
                  placeholder="State engineering justification, test validation review reference, or flight qualification sign-off notes..."
                  value={releaseRationale}
                  onChange={(e) => setReleaseRationale(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-zinc-100 text-xs focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="p-3 bg-zinc-950 rounded border border-zinc-800 space-y-1 text-[11px] font-mono text-zinc-400">
                <div>Target Evaluation ID: {evaluation?.id}</div>
                <div>Authoritative Revision: v{evaluation?.project_revision}</div>
                <div>State Fingerprint: {evaluation?.state_fingerprint.slice(0, 16)}…</div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsAuthorizeModalOpen(false)}
                className="text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={() => authorizeMutation.mutate()}
                disabled={
                  authorizeMutation.isPending ||
                  !releaseTag.trim() ||
                  releaseRationale.trim().length < 5
                }
                className="text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-medium disabled:opacity-50"
              >
                {authorizeMutation.isPending ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                    Freezing Baseline...
                  </>
                ) : (
                  <>
                    <Lock className="w-3.5 h-3.5 mr-1.5" />
                    Sign Off & Freeze Baseline
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
