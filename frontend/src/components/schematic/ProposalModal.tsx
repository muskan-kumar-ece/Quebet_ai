"use client";

import React, { useState } from "react";
import { EngineeringProposal } from "./types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  CheckCircle2,
  AlertTriangle,
  PlusCircle,
  ArrowRight,
  ShieldCheck,
  X,
  Sparkles,
} from "lucide-react";

interface ProposalModalProps {
  proposal: EngineeringProposal | null;
  isOpen: boolean;
  onClose: () => void;
  onApprove: (proposalId: string) => Promise<void>;
  onApply: (proposalId: string) => Promise<void>;
}

export const ProposalModal: React.FC<ProposalModalProps> = ({
  proposal,
  isOpen,
  onClose,
  onApprove,
  onApply,
}) => {
  const [isProcessing, setIsProcessing] = useState(false);

  if (!isOpen || !proposal) return null;

  const isApproved = proposal.status === "APPROVED";
  const isApplied = proposal.status === "APPLIED";
  const isValidated = proposal.status === "VALIDATED";
  const isStale = proposal.status === "STALE";

  const handleApprove = async () => {
    setIsProcessing(true);
    await onApprove(proposal.id);
    setIsProcessing(false);
  };

  const handleApply = async () => {
    setIsProcessing(true);
    await onApply(proposal.id);
    setIsProcessing(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <Card className="w-full max-w-2xl bg-zinc-900 border-zinc-700 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <CardHeader className="p-5 border-b border-zinc-800 flex flex-row items-center justify-between bg-zinc-950/60">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-purple-950/80 border border-purple-700 flex items-center justify-center text-purple-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <CardTitle className="text-base font-semibold text-zinc-100 flex items-center gap-2">
                {proposal.title}
                <Badge
                  variant="outline"
                  className={`text-[10px] uppercase font-mono ${
                    isApplied
                      ? "text-emerald-400 border-emerald-800 bg-emerald-950/50"
                      : isStale
                      ? "text-rose-400 border-rose-800 bg-rose-950/60"
                      : isApproved
                      ? "text-sky-400 border-sky-800 bg-sky-950/50"
                      : "text-amber-400 border-amber-800 bg-amber-950/50"
                  }`}
                >
                  {proposal.status}
                </Badge>
                {proposal.base_revision !== undefined && (
                  <Badge variant="outline" className="text-[10px] text-zinc-400 border-zinc-700 font-mono">
                    Base: v{proposal.base_revision}
                  </Badge>
                )}
              </CardTitle>
              <p className="text-xs text-zinc-400 mt-0.5">{proposal.description || "AI Engineering Staged Proposal"}</p>
            </div>
          </div>
          <Button
            size="sm"
            variant="ghost"
            className="h-8 w-8 p-0 text-zinc-400 hover:text-white"
            onClick={onClose}
          >
            <X className="w-4 h-4" />
          </Button>
        </CardHeader>

        <CardContent className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
          {/* Engineering Safety Rule Banner */}
          <div className="p-3 rounded-lg bg-sky-950/40 border border-sky-800/80 text-xs text-sky-300 flex items-start gap-2.5">
            <ShieldCheck className="w-4 h-4 mt-0.5 text-sky-400 flex-shrink-0" />
            <div>
              <span className="font-semibold block mb-0.5">Engineering Verification Gate</span>
              AI recommendations cannot mutate the electrical circuit without explicit user review, deterministic validation, and user sign-off.
            </div>
          </div>

          {/* Proposed Structural Changes (Engineering Diff) */}
          <div className="space-y-3">
            <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider block">
              Proposed Operations Diff ({proposal.operations.length})
            </span>

            <div className="space-y-2">
              {proposal.operations.map((op, idx) => {
                const payload = op.payload || {};
                return (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 text-xs space-y-1"
                  >
                    <div className="flex items-center gap-2">
                      <PlusCircle className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="font-mono font-bold text-zinc-200 uppercase">
                        {op.op_type.replace("_", " ")}
                      </span>
                    </div>

                    {op.op_type === "add_component" && (
                      <div className="text-zinc-400 pl-5 text-[11px] font-mono">
                        + Add <span className="text-sky-300 font-bold">{payload.ref_des}</span> (
                        {payload.component_type}, {payload.value}, {payload.package || "standard package"})
                      </div>
                    )}

                    {op.op_type === "add_net" && (
                      <div className="text-zinc-400 pl-5 text-[11px] font-mono">
                        + Create Net <span className="text-emerald-300 font-bold">{payload.name}</span> (
                        {payload.net_type || "signal"})
                      </div>
                    )}

                    {op.op_type === "add_connection" && (
                      <div className="text-zinc-400 pl-5 text-[11px] font-mono flex items-center gap-1.5">
                        <span>+ Connect</span>
                        <span className="text-sky-300 font-bold">
                          {payload.ref_des || payload.component_ref}.Pin {payload.pin_number}
                        </span>
                        <ArrowRight className="w-3 h-3 text-zinc-600" />
                        <span className="text-emerald-300 font-bold">{payload.net_name}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Explicit Engineering Assumptions */}
          {proposal.assumptions && proposal.assumptions.length > 0 && (
            <div className="space-y-2">
              <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider block">
                Explicit Engineering Assumptions
              </span>
              <div className="space-y-1.5">
                {proposal.assumptions.map((a, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded bg-zinc-950/70 border border-zinc-800/80 text-xs flex items-center justify-between"
                  >
                    <div>
                      <span className="font-medium text-zinc-300">{a.field}: </span>
                      <span className="text-zinc-400 font-mono">{a.value}</span>
                    </div>
                    {a.confidence && (
                      <Badge variant="outline" className="text-[10px] text-sky-400 border-sky-800 font-mono">
                        {Math.round(a.confidence * 100)}% Conf.
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* STALE Proposal Warning */}
          {isStale && (
            <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800 text-xs text-rose-300 flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 mt-0.5 text-rose-400 flex-shrink-0" />
              <div>
                <span className="font-semibold block mb-0.5">Proposal is Stale</span>
                This proposal was formulated against base revision v{proposal.base_revision}, but the circuit topology has changed. Quebet AI enforces deterministic stale proposal rejection to prevent race conditions and invalid graph mutations. Please re-generate an updated proposal.
              </div>
            </div>
          )}

          {/* Findings Resolved vs Introduced */}
          {((proposal.findings_resolved && proposal.findings_resolved.length > 0) ||
            (proposal.findings_introduced && proposal.findings_introduced.length > 0)) && (
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2.5 rounded bg-emerald-950/20 border border-emerald-900/40">
                <span className="text-[10px] font-bold text-emerald-400 uppercase block mb-1">
                  Findings Resolved ({proposal.findings_resolved?.length || 0})
                </span>
                {proposal.findings_resolved?.map((fId) => (
                  <div key={fId} className="text-emerald-300 font-mono text-[11px]">
                    ✓ {fId}
                  </div>
                ))}
              </div>
              <div className="p-2.5 rounded bg-rose-950/20 border border-rose-900/40">
                <span className="text-[10px] font-bold text-rose-400 uppercase block mb-1">
                  Findings Introduced ({proposal.findings_introduced?.length || 0})
                </span>
                {(!proposal.findings_introduced || proposal.findings_introduced.length === 0) ? (
                  <span className="text-emerald-400 text-[10px]">0 new violations</span>
                ) : (
                  proposal.findings_introduced.map((fId) => (
                    <div key={fId} className="text-rose-300 font-mono text-[11px]">
                      ⚠ {fId}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Validation Result */}
          {proposal.validation_result && (
            <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-800/60 text-xs flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-emerald-300 font-medium">Deterministic Validation Check</span>
              </div>
              <Badge className="bg-emerald-950 border-emerald-700 text-emerald-400 font-mono text-[10px]">
                PASSED
              </Badge>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-800">
            <Button
              variant="outline"
              size="sm"
              onClick={onClose}
              className="text-zinc-400 border-zinc-700 hover:bg-zinc-800"
            >
              Close
            </Button>

            {!isApproved && !isApplied && !isStale && (
              <Button
                size="sm"
                onClick={handleApprove}
                disabled={isProcessing}
                className="bg-sky-600 hover:bg-sky-500 text-white font-medium"
              >
                {isProcessing ? "Approving..." : "Approve Proposal"}
              </Button>
            )}

            {isApproved && !isApplied && !isStale && (
              <Button
                size="sm"
                onClick={handleApply}
                disabled={isProcessing}
                className="bg-emerald-600 hover:bg-emerald-500 text-white font-medium"
              >
                {isProcessing ? "Applying..." : "Apply to Circuit"}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
