"use client";

import React, { useState } from "react";
import {
  X,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  ArrowRight,
  Loader2,
  Cpu,
  Zap,
  Activity,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import {
  EngineeringSubsystem,
  EngineeringSystemInterface,
  FailurePropagationResult,
} from "./types";

interface FailurePropagationModalProps {
  systemId: string;
  subsystems: EngineeringSubsystem[];
  interfaces: EngineeringSystemInterface[];
  onClose: () => void;
}

export const FailurePropagationModal: React.FC<FailurePropagationModalProps> = ({
  systemId,
  subsystems,
  interfaces,
  onClose,
}) => {
  const [selectedSubsystemId, setSelectedSubsystemId] = useState<string>(subsystems[0]?.id || "");
  const [failureType, setFailureType] = useState<string>("TOTAL_LOSS_OF_FUNCTION");
  const [isSimulating, setIsSimulating] = useState(false);
  const [result, setResult] = useState<FailurePropagationResult | null>(null);

  const handleSimulate = async () => {
    if (!selectedSubsystemId) return;
    setIsSimulating(true);
    try {
      const res = await apiClient.post(`/systems/${systemId}/failure-analysis`, {
        failed_subsystem_id: selectedSubsystemId,
        failure_type: failureType,
      });
      if (res.data?.data) {
        setResult(res.data.data);
      }
    } catch (e) {
      console.error("Simulation failed", e);
    } finally {
      setIsSimulating(false);
    }
  };

  const subById = new Map(subsystems.map((s) => [s.id, s]));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-150">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/80">
          <div className="flex items-center gap-2.5">
            <ShieldAlert className="w-5 h-5 text-red-400" />
            <div>
              <h2 className="text-sm font-bold text-zinc-100">
                Deterministic Failure Propagation Simulator
              </h2>
              <p className="text-[11px] text-zinc-400">
                Simulate failure propagation across subsystem boundaries and verify containment barriers.
              </p>
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
        </div>

        {/* Content */}
        <div className="p-5 overflow-y-auto space-y-5 flex-1">
          {/* Form */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-zinc-950/60 p-4 rounded-lg border border-zinc-800/80">
            <div>
              <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block mb-1.5">
                Target Subsystem (Root Cause)
              </label>
              <select
                value={selectedSubsystemId}
                onChange={(e) => setSelectedSubsystemId(e.target.value)}
                className="w-full h-9 bg-zinc-900 border border-zinc-700 rounded px-2.5 text-xs text-zinc-200 focus:outline-none focus:border-red-500 font-mono"
              >
                {subsystems.map((sub) => (
                  <option key={sub.id} value={sub.id}>
                    [{sub.subsystem_type}] {sub.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block mb-1.5">
                Failure Mechanism
              </label>
              <select
                value={failureType}
                onChange={(e) => setFailureType(e.target.value)}
                className="w-full h-9 bg-zinc-900 border border-zinc-700 rounded px-2.5 text-xs text-zinc-200 focus:outline-none focus:border-red-500 font-mono"
              >
                <option value="TOTAL_LOSS_OF_FUNCTION">TOTAL_LOSS_OF_FUNCTION</option>
                <option value="SHORT_CIRCUIT">SHORT_CIRCUIT (Power Fault)</option>
                <option value="OVERCURRENT_FAULT">OVERCURRENT_FAULT</option>
                <option value="VOLTAGE_SPIKE">VOLTAGE_SPIKE</option>
                <option value="BUS_HANG">BUS_HANG (Communication Lockup)</option>
              </select>
            </div>

            <div className="sm:col-span-2 flex justify-end">
              <Button
                size="sm"
                onClick={handleSimulate}
                disabled={isSimulating || !selectedSubsystemId}
                className="h-9 px-4 bg-red-600 hover:bg-red-500 text-white font-medium text-xs flex items-center gap-1.5"
              >
                {isSimulating ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Propagating...</span>
                  </>
                ) : (
                  <>
                    <Activity className="w-3.5 h-3.5" />
                    <span>Run Failure Simulation</span>
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Results Display */}
          {result && (
            <div className="space-y-4 pt-2">
              {/* Containment Barriers */}
              <div className="bg-zinc-950/80 p-4 rounded-lg border border-zinc-800 space-y-2">
                <span className="text-xs font-bold text-zinc-300 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  Containment Barriers Active
                </span>
                {result.containment_barriers.length === 0 ? (
                  <p className="text-xs text-amber-400/90 italic">
                    No physical or galvanic barriers stopped this failure. Unchecked propagation across subsystem boundaries.
                  </p>
                ) : (
                  <div className="space-y-1.5">
                    {result.containment_barriers.map((barrier, idx) => (
                      <div
                        key={idx}
                        className="p-2.5 rounded bg-emerald-950/20 border border-emerald-800/60 flex items-start gap-2 text-xs"
                      >
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-semibold text-emerald-300">
                            {barrier.barrier}
                          </span>
                          {barrier.protected_subsystem_name && (
                            <span className="text-zinc-400 block text-[11px]">
                              Protected: {barrier.protected_subsystem_name}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Blast Radius Summary */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-zinc-950 rounded border border-zinc-800">
                  <span className="text-[11px] font-mono text-zinc-500 uppercase block mb-1">
                    Downstream Subsystems
                  </span>
                  <span className="text-xl font-bold font-mono text-red-400">
                    {result.downstream_affected_subsystems.length}
                  </span>
                  <div className="mt-2 space-y-1">
                    {result.downstream_affected_subsystems.map((id) => (
                      <div key={id} className="text-xs text-zinc-300 font-mono">
                        • {subById.get(id)?.name || id}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="p-3 bg-zinc-950 rounded border border-zinc-800">
                  <span className="text-[11px] font-mono text-zinc-500 uppercase block mb-1">
                    Affected Interfaces & Rails
                  </span>
                  <div className="flex items-center gap-4 text-xl font-bold font-mono text-amber-400">
                    <span>{result.affected_interfaces.length} ifaces</span>
                    <span>{result.affected_power_domains.length} rails</span>
                  </div>
                </div>
              </div>

              {/* Loss of Functions */}
              <div className="space-y-1.5">
                <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider block">
                  Cascading Functional Losses
                </span>
                <div className="space-y-1">
                  {result.loss_of_functions.map((loss, idx) => (
                    <div
                      key={idx}
                      className="p-2 rounded bg-zinc-950/40 border border-zinc-800/80 text-xs text-zinc-300 flex items-center gap-2 font-mono"
                    >
                      <span className="text-red-500 font-bold">✕</span>
                      <span>{loss}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
