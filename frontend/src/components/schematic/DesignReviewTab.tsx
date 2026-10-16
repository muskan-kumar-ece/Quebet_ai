"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Plus,
  FileCheck,
  Layers,
  Activity,
  Gauge,
  Thermometer,
  Wrench,
  Loader2,
  Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api";
import {
  DesignReview,
  VerificationMatrixData,
  VerificationRequirement,
  FailureMode,
  TestPoint,
} from "./types";
import { TraceabilityModal } from "./TraceabilityModal";

interface DesignReviewTabProps {
  circuitId: string | null;
  currentCircuitVersion: number;
}

const DEFAULT_REVIEW_STATUS = { label: "DRAFT", color: "text-zinc-400 bg-zinc-900 border-zinc-700", icon: HelpCircle };
const REVIEW_STATUS_CONFIG: Record<
  string,
  { label: string; color: string; icon: any }
> = {
  DRAFT: DEFAULT_REVIEW_STATUS,
  ANALYSIS_COMPLETE: { label: "ANALYZED", color: "text-sky-400 bg-sky-950/60 border-sky-800", icon: Activity },
  REVIEW_IN_PROGRESS: { label: "IN PROGRESS", color: "text-blue-400 bg-blue-950/60 border-blue-800", icon: RefreshCw },
  VERIFICATION_REQUIRED: { label: "VERIFICATION REQUIRED", color: "text-amber-400 bg-amber-950/60 border-amber-800", icon: AlertTriangle },
  PARTIALLY_VERIFIED: { label: "PARTIALLY VERIFIED", color: "text-teal-400 bg-teal-950/60 border-teal-800", icon: ShieldCheck },
  VERIFIED: { label: "VERIFIED", color: "text-emerald-400 bg-emerald-950/60 border-emerald-800", icon: CheckCircle2 },
  BLOCKED: { label: "BLOCKED", color: "text-red-400 bg-red-950/60 border-red-800", icon: XCircle },
  STALE: { label: "STALE (REV MISMATCH)", color: "text-amber-400 bg-amber-950/60 border-amber-800", icon: ShieldAlert },
};

const DEFAULT_REQ_STATUS = { label: "NOT STARTED", color: "text-zinc-400 bg-zinc-900 border-zinc-700" };
const REQUIREMENT_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  NOT_STARTED: DEFAULT_REQ_STATUS,
  IN_PROGRESS: { label: "IN PROGRESS", color: "text-blue-400 bg-blue-950 border-blue-800" },
  SATISFIED: { label: "SATISFIED", color: "text-emerald-400 bg-emerald-950 border-emerald-800" },
  FAILED: { label: "FAILED", color: "text-red-400 bg-red-950 border-red-800" },
  BLOCKED: { label: "BLOCKED", color: "text-rose-400 bg-rose-950 border-rose-800" },
  UNKNOWN: { label: "UNKNOWN", color: "text-amber-400 bg-amber-950 border-amber-800" },
  NOT_APPLICABLE: { label: "N/A", color: "text-zinc-500 bg-zinc-900/60 border-zinc-800" },
};

export const DesignReviewTab: React.FC<DesignReviewTabProps> = ({
  circuitId,
  currentCircuitVersion,
}) => {
  const queryClient = useQueryClient();
  const [expandedReqId, setExpandedReqId] = useState<string | null>(null);
  const [evidenceFormReqId, setEvidenceFormReqId] = useState<string | null>(null);
  const [traceTarget, setTraceTarget] = useState<{
    type: "finding" | "requirement" | "evidence";
    id: string;
  } | null>(null);

  // Evidence Form State
  const [evidenceType, setEvidenceType] = useState<string>("MEASUREMENT");
  const [evidenceSource, setEvidenceSource] = useState<string>("");
  const [evidenceDesc, setEvidenceDesc] = useState<string>("");
  const [evidenceVal, setEvidenceVal] = useState<string>("");
  const [evidenceUnit, setEvidenceUnit] = useState<string>("");
  const [evidenceRef, setEvidenceRef] = useState<string>("");
  const [formError, setFormError] = useState<string | null>(null);

  // Fetch or trigger latest Design Review
  const {
    data: review,
    isLoading: isReviewLoading,
    refetch: refetchReview,
  } = useQuery<DesignReview>({
    queryKey: ["design-review", circuitId],
    queryFn: async () => {
      if (!circuitId) throw new Error("No circuit ID");
      const res = await apiClient.post(`/circuits/${circuitId}/design-review`);
      return res.data?.data;
    },
    enabled: !!circuitId,
  });

  // Fetch Verification Matrix
  const { data: matrixData } = useQuery<VerificationMatrixData>({
    queryKey: ["verification-matrix", review?.id],
    queryFn: async () => {
      if (!review?.id) throw new Error("No review ID");
      const res = await apiClient.get(`/design-reviews/${review.id}/verification-matrix`);
      return res.data?.data;
    },
    enabled: !!review?.id,
  });

  // Mutation: Add Evidence
  const addEvidenceMutation = useMutation({
    mutationFn: async ({
      reqId,
      payload,
    }: {
      reqId: string;
      payload: any;
    }) => {
      const res = await apiClient.post(
        `/verification-requirements/${reqId}/evidence`,
        payload
      );
      return res.data?.data;
    },
    onSuccess: () => {
      setEvidenceFormReqId(null);
      setEvidenceSource("");
      setEvidenceDesc("");
      setEvidenceVal("");
      setEvidenceUnit("");
      setEvidenceRef("");
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["design-review", circuitId] });
      queryClient.invalidateQueries({ queryKey: ["verification-matrix", review?.id] });
    },
    onError: (err: any) => {
      setFormError(
        err.response?.data?.detail?.message ||
          err.response?.data?.detail ||
          "Failed to submit evidence."
      );
    },
  });

  // Mutation: Update Requirement Status
  const updateStatusMutation = useMutation({
    mutationFn: async ({
      reqId,
      status,
      reason,
      notApplicableReason,
    }: {
      reqId: string;
      status: string;
      reason?: string;
      notApplicableReason?: string;
    }) => {
      const res = await apiClient.patch(
        `/verification-requirements/${reqId}/status`,
        {
          status,
          reason,
          not_applicable_reason: notApplicableReason,
        }
      );
      return res.data?.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["design-review", circuitId] });
      queryClient.invalidateQueries({ queryKey: ["verification-matrix", review?.id] });
    },
    onError: (err: any) => {
      alert(
        err.response?.data?.detail?.message ||
          err.response?.data?.detail ||
          "Failed to update status."
      );
    },
  });

  // Mutation: Refresh Review against latest revision
  const refreshReviewMutation = useMutation({
    mutationFn: async () => {
      if (!review?.id) return;
      const res = await apiClient.post(`/design-reviews/${review.id}/refresh`);
      return res.data?.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["design-review", circuitId] });
    },
  });

  if (isReviewLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-zinc-500 space-y-3">
        <Loader2 className="w-6 h-6 animate-spin text-sky-400" />
        <span className="text-xs font-mono">Deriving failure modes & verification requirements...</span>
      </div>
    );
  }

  if (!review) {
    return (
      <div className="p-4 text-center text-zinc-500 text-xs font-mono">
        No active design review found for this circuit.
      </div>
    );
  }

  const isStale = review.is_stale || review.circuit_revision !== currentCircuitVersion;
  const statusCfg = REVIEW_STATUS_CONFIG[isStale ? "STALE" : review.status] ?? DEFAULT_REVIEW_STATUS;
  const StatusIcon = statusCfg.icon;

  return (
    <div className="space-y-4">
      {/* 1. Header / Revision & Status Bar */}
      <div className="p-3 bg-zinc-900/60 border border-zinc-800 rounded-lg space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold text-zinc-200">
              Design Review
            </span>
            <Badge
              variant="outline"
              className={`text-[10px] font-mono flex items-center gap-1 ${statusCfg.color}`}
            >
              <StatusIcon className="w-3 h-3" />
              {statusCfg.label}
            </Badge>
          </div>
          <div className="text-[11px] font-mono text-zinc-400">
            Rev <span className="text-zinc-200 font-bold">v{review.circuit_revision}</span>
          </div>
        </div>

        {/* Stale Warning Banner */}
        {isStale && (
          <div className="p-2.5 bg-amber-950/40 border border-amber-800/80 rounded flex items-center justify-between text-xs text-amber-200 font-mono">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              <span>
                Circuit version has advanced to v{currentCircuitVersion}. Review is bound to v{review.circuit_revision}.
              </span>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => refreshReviewMutation.mutate()}
              disabled={refreshReviewMutation.isPending}
              className="h-7 text-xs border-amber-700 bg-amber-900/40 hover:bg-amber-800 text-amber-100 flex items-center gap-1 font-mono"
            >
              <RefreshCw className={`w-3 h-3 ${refreshReviewMutation.isPending ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        )}

        {/* Matrix Counters */}
        {matrixData && (
          <div className="grid grid-cols-4 gap-1.5 pt-1 text-center font-mono">
            <div className="p-1.5 bg-zinc-950/60 rounded border border-zinc-800/60">
              <div className="text-[10px] text-zinc-500">Satisfied</div>
              <div className="text-xs font-bold text-emerald-400">{matrixData.satisfied_count}</div>
            </div>
            <div className="p-1.5 bg-zinc-950/60 rounded border border-zinc-800/60">
              <div className="text-[10px] text-zinc-500">In Progress</div>
              <div className="text-xs font-bold text-blue-400">{matrixData.in_progress_count}</div>
            </div>
            <div className="p-1.5 bg-zinc-950/60 rounded border border-zinc-800/60">
              <div className="text-[10px] text-zinc-500">Unknown</div>
              <div className="text-xs font-bold text-amber-400">{matrixData.unknown_count}</div>
            </div>
            <div className="p-1.5 bg-zinc-950/60 rounded border border-zinc-800/60">
              <div className="text-[10px] text-zinc-500">Blocked</div>
              <div className="text-xs font-bold text-red-400">{matrixData.blocked_count}</div>
            </div>
          </div>
        )}
      </div>

      {/* 2. Unresolved Deterministic Findings Warning */}
      {review.unresolved_findings_count > 0 && (
        <div className="p-2.5 bg-red-950/30 border border-red-900/60 rounded-lg text-xs font-mono text-red-300 flex items-center gap-2">
          <XCircle className="w-4 h-4 text-red-400 shrink-0" />
          <span>
            {review.unresolved_findings_count} deterministic finding(s) remain unresolved. Review cannot be verified until resolved or addressed.
          </span>
        </div>
      )}

      {/* 3. Deterministic Failure Modes Section */}
      <div className="space-y-2">
        <div className="flex items-center justify-between px-1">
          <span className="text-[11px] font-mono font-bold text-zinc-400 uppercase tracking-wider">
            Failure Analysis ({review.failure_modes.length})
          </span>
          <span className="text-[10px] text-zinc-500 font-mono">Evidence-Based</span>
        </div>

        <div className="space-y-1.5">
          {review.failure_modes.map((fm) => (
            <div
              key={fm.id}
              className="p-2.5 bg-zinc-900/40 border border-zinc-800 rounded-lg space-y-1.5 font-mono"
            >
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-zinc-200">{fm.category}</span>
                <div className="flex items-center gap-1.5">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setTraceTarget({ type: "finding", id: fm.related_findings[0] || fm.id })}
                    className="h-5 px-1.5 text-[9px] text-sky-400 hover:bg-sky-950/40 hover:text-sky-300 font-mono"
                  >
                    Trace
                  </Button>
                  <Badge
                    variant="outline"
                    className={`text-[9px] ${
                      fm.severity === "CRITICAL"
                        ? "text-red-400 border-red-800 bg-red-950/40"
                        : "text-amber-400 border-amber-800 bg-amber-950/40"
                    }`}
                  >
                    {fm.severity}
                  </Badge>
                </div>
              </div>

              <div className="text-[11px] text-zinc-400">{fm.trigger}</div>

              <div className="text-[10px] text-zinc-500 bg-zinc-950/60 p-1.5 rounded border border-zinc-800/40">
                <span className="text-zinc-400 font-semibold">Mechanism:</span> {fm.mechanism}
              </div>

              <div className="flex flex-wrap gap-1 pt-0.5">
                {fm.evidence.map((ev, i) => (
                  <span
                    key={i}
                    className="text-[9px] px-1.5 py-0.5 bg-zinc-800 text-zinc-400 rounded"
                  >
                    {ev}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 4. Verification Requirements Matrix & Evidence Entry */}
      <div className="space-y-2">
        <div className="flex items-center justify-between px-1">
          <span className="text-[11px] font-mono font-bold text-zinc-400 uppercase tracking-wider">
            Verification Matrix ({review.verification_requirements.length})
          </span>
          <span className="text-[10px] text-zinc-500 font-mono">VR001+ Rules</span>
        </div>

        <div className="space-y-2">
          {review.verification_requirements.map((req) => {
            const isExpanded = expandedReqId === req.id;
            const isEvidenceFormOpen = evidenceFormReqId === req.id;
            const reqStatusCfg =
              REQUIREMENT_STATUS_CONFIG[req.status] ?? DEFAULT_REQ_STATUS;

            return (
              <div
                key={req.id}
                className="bg-zinc-900/40 border border-zinc-800 rounded-lg overflow-hidden font-mono"
              >
                {/* Requirement Card Header */}
                <div
                  onClick={() => setExpandedReqId(isExpanded ? null : req.id)}
                  className="p-2.5 flex items-center justify-between cursor-pointer hover:bg-zinc-800/30 transition-colors"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-sky-400">{req.code}</span>
                      <Badge
                        variant="outline"
                        className={`text-[9px] ${reqStatusCfg.color}`}
                      >
                        {reqStatusCfg.label}
                      </Badge>
                      {req.is_mandatory && (
                        <span className="text-[9px] text-red-400 font-bold">*MANDATORY</span>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          setTraceTarget({ type: "requirement", id: req.id });
                        }}
                        className="h-5 px-1.5 text-[9px] text-purple-400 hover:bg-purple-950/40 hover:text-purple-300 font-mono"
                      >
                        Trace
                      </Button>
                    </div>
                    <div className="text-xs text-zinc-200">{req.title}</div>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-zinc-400 shrink-0" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-zinc-400 shrink-0" />
                  )}
                </div>

                {/* Expanded Detail Panel */}
                {isExpanded && (
                  <div className="p-3 border-t border-zinc-800 bg-zinc-950/40 space-y-3 text-xs">
                    {/* Reason & Method */}
                    <div className="space-y-1">
                      <div className="text-zinc-400">
                        <span className="text-zinc-500 font-semibold">Reason:</span> {req.reason}
                      </div>
                      <div className="text-zinc-400">
                        <span className="text-zinc-500 font-semibold">Method:</span>{" "}
                        <Badge variant="outline" className="text-[10px] text-zinc-300">
                          {req.method}
                        </Badge>
                      </div>
                      <div className="text-zinc-400">
                        <span className="text-zinc-500 font-semibold">Condition:</span>{" "}
                        <Badge variant="outline" className="text-[10px] text-purple-300 border-purple-900">
                          {req.operating_condition}
                        </Badge>
                      </div>
                    </div>

                    {/* Required Evidence */}
                    <div className="space-y-1">
                      <span className="text-[10px] text-zinc-500 uppercase tracking-wider block font-semibold">
                        Required Evidence
                      </span>
                      <ul className="list-disc list-inside text-zinc-400 space-y-0.5 text-[11px]">
                        {req.required_evidence.map((rev, idx) => (
                          <li key={idx}>{rev}</li>
                        ))}
                      </ul>
                    </div>

                    {/* Submitted Evidence Items */}
                    {req.evidence_items && req.evidence_items.length > 0 && (
                      <div className="space-y-1.5 pt-1">
                        <span className="text-[10px] text-zinc-500 uppercase tracking-wider block font-semibold">
                          Traceable Submitted Evidence ({req.evidence_items.length})
                        </span>
                        {req.evidence_items.map((ev) => (
                          <div
                            key={ev.id}
                            className="p-2 bg-zinc-900/60 border border-zinc-800/80 rounded space-y-1"
                          >
                            <div className="flex items-center justify-between text-[11px]">
                              <span className="font-bold text-zinc-300">{ev.source}</span>
                              <div className="flex items-center gap-1.5">
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => setTraceTarget({ type: "evidence", id: ev.id })}
                                  className="h-4 px-1.5 text-[8px] text-teal-400 hover:bg-teal-950/40 hover:text-teal-300 font-mono"
                                >
                                  Trace
                                </Button>
                                <Badge variant="outline" className="text-[9px] text-emerald-400 border-emerald-800">
                                  {ev.status}
                                </Badge>
                              </div>
                            </div>
                            <div className="text-[11px] text-zinc-400">{ev.description}</div>
                            {ev.value && (
                              <div className="text-[10px] text-sky-400 font-bold">
                                Value: {ev.value} {ev.unit || ""}
                              </div>
                            )}
                            {ev.reference && (
                              <div className="text-[9px] text-zinc-500">Ref: {ev.reference}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Unknowns warning if any */}
                    {req.unknowns && req.unknowns.length > 0 && (
                      <div className="p-2 bg-amber-950/30 border border-amber-900/60 rounded text-[11px] text-amber-300">
                        <span className="font-bold">Unresolved Unknowns:</span> {req.unknowns.join(", ")}
                      </div>
                    )}

                    {/* Evidence Submission Form Toggle */}
                    {!isEvidenceFormOpen ? (
                      <div className="flex items-center gap-2 pt-1">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setEvidenceFormReqId(req.id)}
                          className="h-7 text-xs bg-zinc-900 hover:bg-zinc-800 border-zinc-700 text-zinc-200 flex items-center gap-1 font-mono"
                        >
                          <Plus className="w-3 h-3 text-sky-400" />
                          Add Evidence
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            updateStatusMutation.mutate({
                              reqId: req.id,
                              status: "SATISFIED",
                              reason: "Marked verified based on reviewed criteria",
                            })
                          }
                          disabled={isStale || req.unknowns.length > 0}
                          className="h-7 text-xs bg-emerald-950/40 hover:bg-emerald-900 border-emerald-800 text-emerald-300 font-mono"
                        >
                          Mark Satisfied
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            const reason = prompt("Enter engineering rationale for marking NOT_APPLICABLE:");
                            if (reason) {
                              updateStatusMutation.mutate({
                                reqId: req.id,
                                status: "NOT_APPLICABLE",
                                notApplicableReason: reason,
                              });
                            }
                          }}
                          disabled={isStale}
                          className="h-7 text-xs bg-zinc-900 hover:bg-zinc-800 border-zinc-700 text-zinc-400 font-mono"
                        >
                          Mark N/A
                        </Button>
                      </div>
                    ) : (
                      <div className="p-3 bg-zinc-900/80 border border-zinc-700 rounded-lg space-y-2.5">
                        <div className="flex items-center justify-between text-xs font-bold text-zinc-200">
                          <span>Submit Traceable Evidence</span>
                          <button
                            onClick={() => setEvidenceFormReqId(null)}
                            className="text-zinc-500 hover:text-zinc-300"
                          >
                            Cancel
                          </button>
                        </div>

                        {formError && (
                          <div className="p-2 bg-red-950 border border-red-800 rounded text-[11px] text-red-300">
                            {formError}
                          </div>
                        )}

                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="text-[10px] text-zinc-400 block mb-1">Type</label>
                            <select
                              value={evidenceType}
                              onChange={(e) => setEvidenceType(e.target.value)}
                              className="w-full h-7 bg-zinc-950 border border-zinc-800 rounded px-2 text-xs text-zinc-200"
                            >
                              <option value="MEASUREMENT">MEASUREMENT</option>
                              <option value="DATASHEET">DATASHEET</option>
                              <option value="CALCULATION">CALCULATION</option>
                              <option value="SCHEMATIC_INSPECTION">SCHEMATIC_INSPECTION</option>
                              <option value="TEST_REPORT">TEST_REPORT</option>
                            </select>
                          </div>
                          <div>
                            <label className="text-[10px] text-zinc-400 block mb-1">Source / Instrument</label>
                            <input
                              type="text"
                              value={evidenceSource}
                              onChange={(e) => setEvidenceSource(e.target.value)}
                              placeholder="e.g. Fluke 87V DMM"
                              className="w-full h-7 bg-zinc-950 border border-zinc-800 rounded px-2 text-xs text-zinc-200"
                            />
                          </div>
                        </div>

                        <div>
                          <label className="text-[10px] text-zinc-400 block mb-1">Description</label>
                          <textarea
                            value={evidenceDesc}
                            onChange={(e) => setEvidenceDesc(e.target.value)}
                            placeholder="Detailed engineering observation..."
                            rows={2}
                            className="w-full bg-zinc-950 border border-zinc-800 rounded p-1.5 text-xs text-zinc-200"
                          />
                        </div>

                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <label className="text-[10px] text-zinc-400 block mb-1">Value</label>
                            <input
                              type="text"
                              value={evidenceVal}
                              onChange={(e) => setEvidenceVal(e.target.value)}
                              placeholder="e.g. 3.31"
                              className="w-full h-7 bg-zinc-950 border border-zinc-800 rounded px-2 text-xs text-zinc-200"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] text-zinc-400 block mb-1">Unit</label>
                            <input
                              type="text"
                              value={evidenceUnit}
                              onChange={(e) => setEvidenceUnit(e.target.value)}
                              placeholder="V, mA, °C"
                              className="w-full h-7 bg-zinc-950 border border-zinc-800 rounded px-2 text-xs text-zinc-200"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] text-zinc-400 block mb-1">Reference</label>
                            <input
                              type="text"
                              value={evidenceRef}
                              onChange={(e) => setEvidenceRef(e.target.value)}
                              placeholder="Doc/Log page"
                              className="w-full h-7 bg-zinc-950 border border-zinc-800 rounded px-2 text-xs text-zinc-200"
                            />
                          </div>
                        </div>

                        <Button
                          size="sm"
                          onClick={() =>
                            addEvidenceMutation.mutate({
                              reqId: req.id,
                              payload: {
                                evidence_type: evidenceType,
                                source: evidenceSource,
                                description: evidenceDesc,
                                value: evidenceVal || null,
                                unit: evidenceUnit || null,
                                reference: evidenceRef || null,
                              },
                            })
                          }
                          disabled={
                            addEvidenceMutation.isPending ||
                            !evidenceSource.trim() ||
                            !evidenceDesc.trim() ||
                            isStale
                          }
                          className="w-full h-7 bg-sky-600 hover:bg-sky-500 text-white font-mono text-xs"
                        >
                          {addEvidenceMutation.isPending ? "Submitting..." : "Save Evidence"}
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 5. Laboratory Test Points */}
      {review.test_points && review.test_points.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between px-1">
            <span className="text-[11px] font-mono font-bold text-zinc-400 uppercase tracking-wider">
              Suggested Test Points ({review.test_points.length})
            </span>
            <span className="text-[10px] text-zinc-500 font-mono">Bench Measurements</span>
          </div>

          <div className="space-y-1.5">
            {review.test_points.map((tp) => (
              <div
                key={tp.id}
                className="p-2.5 bg-zinc-900/40 border border-zinc-800 rounded-lg space-y-1 font-mono text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-purple-400">{tp.code}</span>
                  <Badge variant="outline" className="text-[9px] text-zinc-400">
                    {tp.instrumentation}
                  </Badge>
                </div>
                <div className="text-zinc-200 font-semibold">{tp.measurement}</div>
                <div className="text-[10px] text-zinc-500">
                  <span className="text-zinc-400 font-semibold">Expected:</span> {tp.expected_basis}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {traceTarget && (
        <TraceabilityModal
          type={traceTarget.type}
          id={traceTarget.id}
          onClose={() => setTraceTarget(null)}
        />
      )}
    </div>
  );
};
