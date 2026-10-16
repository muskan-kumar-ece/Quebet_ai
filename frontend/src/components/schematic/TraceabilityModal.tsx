"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  X,
  FileText,
  Database,
  Cpu,
  ShieldCheck,
  AlertTriangle,
  ExternalLink,
  Loader2,
  CheckCircle2,
  Layers,
  Search,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  EngineeringSource,
  EngineeringKnowledgeRecord,
  FindingTraceabilityData,
  RequirementTraceabilityData,
  EvidenceTraceabilityData,
} from "./types";

interface TraceabilityModalProps {
  type: "finding" | "requirement" | "evidence";
  id: string;
  onClose: () => void;
}

export const TraceabilityModal: React.FC<TraceabilityModalProps> = ({
  type,
  id,
  onClose,
}) => {
  const [selectedSource, setSelectedSource] = useState<EngineeringSource | null>(null);
  const [selectedKnowledge, setSelectedKnowledge] = useState<EngineeringKnowledgeRecord | null>(null);

  // Fetch traceability data based on type
  const { data: traceData, isLoading, error } = useQuery<any>({
    queryKey: ["traceability", type, id],
    queryFn: async () => {
      let endpoint = "";
      if (type === "finding") {
        endpoint = `/findings/${id}/traceability`;
      } else if (type === "requirement") {
        endpoint = `/verification-requirements/${id}/traceability`;
      } else if (type === "evidence") {
        endpoint = `/evidence/${id}/traceability`;
      }
      const res = await apiClient.get(endpoint);
      return res.data?.data;
    },
    enabled: !!id,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 font-mono">
      <div className="bg-zinc-950 border border-zinc-800 rounded-xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden text-zinc-200">
        {/* Header */}
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/60">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-sky-400" />
            <div>
              <h2 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                Engineering Traceability Chain
                <Badge variant="outline" className="text-[10px] text-sky-400 border-sky-800 bg-sky-950/40">
                  {type.toUpperCase()}
                </Badge>
              </h2>
              <p className="text-[11px] text-zinc-400 font-normal">
                Verifiable provenance: Source → Knowledge → Calculation → Evidence
              </p>
            </div>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={onClose}
            className="h-8 w-8 p-0 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Content Body */}
        <div className="p-4 overflow-y-auto space-y-4 flex-1">
          {isLoading && (
            <div className="flex flex-col items-center justify-center p-12 text-zinc-500 space-y-2">
              <Loader2 className="w-6 h-6 animate-spin text-sky-400" />
              <span className="text-xs">Traversing provenance graph...</span>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-950/40 border border-red-800 rounded-lg text-xs text-red-300">
              Failed to load traceability details: {(error as any)?.message || "Unknown error"}
            </div>
          )}

          {traceData && (
            <div className="space-y-4">
              {/* 1. Core Subject Summary */}
              {type === "finding" && (
                <div className="p-3 bg-zinc-900/70 border border-zinc-800 rounded-lg space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-sky-400">Rule: {traceData.rule_id}</span>
                    <span className="text-[10px] text-zinc-500">Analysis: {traceData.analysis_id?.slice(0, 8)}...</span>
                  </div>
                  <div className="text-xs text-zinc-300">
                    <span className="text-zinc-500">Affected Components:</span>{" "}
                    {traceData.affected_components?.join(", ") || "None"}
                  </div>
                  {traceData.calculation_result && (
                    <div className="p-2 bg-zinc-950 rounded border border-zinc-800/80 text-[11px] text-zinc-300">
                      <div className="text-[10px] text-zinc-500 mb-1 font-bold">Physical Calculation Basis:</div>
                      <pre className="text-[10px] text-emerald-400 overflow-x-auto">
                        {JSON.stringify(traceData.calculation_result, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              {type === "requirement" && (
                <div className="p-3 bg-zinc-900/70 border border-zinc-800 rounded-lg space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-sky-400">{traceData.requirement_code}</span>
                    <span className="text-[10px] text-zinc-400">{traceData.evidence_count} evidence item(s)</span>
                  </div>
                  <div className="text-xs text-zinc-300">
                    <span className="text-zinc-500">Triggering Finding:</span> {traceData.related_finding_id || "Direct Rule Evaluation"}
                  </div>
                </div>
              )}

              {type === "evidence" && (
                <div className="p-3 bg-zinc-900/70 border border-zinc-800 rounded-lg space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-teal-400">{traceData.evidence_type}</span>
                    <Badge
                      variant="outline"
                      className={`text-[9px] ${
                        traceData.calibration_status === "CALIBRATED"
                          ? "text-emerald-400 border-emerald-800"
                          : "text-amber-400 border-amber-800"
                      }`}
                    >
                      {traceData.calibration_status}
                    </Badge>
                  </div>
                  <div className="text-zinc-300">{traceData.source}</div>
                  <div className="grid grid-cols-2 gap-2 pt-1 text-[11px] text-zinc-400">
                    <div>Instrument: <span className="text-zinc-200">{traceData.instrument_model || "N/A"}</span></div>
                    <div>Serial: <span className="text-zinc-200">{traceData.instrument_serial || "N/A"}</span></div>
                    <div>Cal Ref: <span className="text-zinc-200">{traceData.calibration_reference || "N/A"}</span></div>
                    <div>Revision Bound: <span className="text-zinc-200">v{traceData.circuit_revision ?? 1}</span></div>
                  </div>
                </div>
              )}

              {/* 2. Knowledge Records Chain */}
              {traceData.knowledge_records && traceData.knowledge_records.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-zinc-400 uppercase tracking-wider">
                    <Database className="w-3.5 h-3.5 text-purple-400" />
                    Verified Knowledge Records ({traceData.knowledge_records.length})
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {traceData.knowledge_records.map((kr: EngineeringKnowledgeRecord) => (
                      <div
                        key={kr.id}
                        onClick={() => setSelectedKnowledge(kr)}
                        className={`p-2.5 rounded-lg border cursor-pointer transition-colors text-xs ${
                          selectedKnowledge?.id === kr.id
                            ? "bg-purple-950/40 border-purple-600"
                            : "bg-zinc-900/40 border-zinc-800 hover:bg-zinc-800/40"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-purple-300">{kr.subject_identifier}</span>
                          <Badge variant="outline" className="text-[9px] text-zinc-400">
                            {kr.status}
                          </Badge>
                        </div>
                        <div className="text-[11px] text-zinc-300 mt-1">
                          {kr.parameter}: <span className="font-bold text-zinc-100">{kr.value} {kr.unit || ""}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 3. Authoritative Sources Chain */}
              {traceData.sources && traceData.sources.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-zinc-400 uppercase tracking-wider">
                    <FileText className="w-3.5 h-3.5 text-blue-400" />
                    Authoritative Sources ({traceData.sources.length})
                  </div>
                  <div className="grid grid-cols-1 gap-2">
                    {traceData.sources.map((src: EngineeringSource) => (
                      <div
                        key={src.id}
                        onClick={() => setSelectedSource(src)}
                        className={`p-2.5 rounded-lg border cursor-pointer transition-colors text-xs ${
                          selectedSource?.id === src.id
                            ? "bg-sky-950/40 border-sky-600"
                            : "bg-zinc-900/40 border-zinc-800 hover:bg-zinc-800/40"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-sky-300">{src.title}</span>
                          <Badge variant="outline" className="text-[9px] text-sky-400 border-sky-800">
                            {src.trust_level}
                          </Badge>
                        </div>
                        <div className="text-[11px] text-zinc-400 mt-1 flex items-center justify-between">
                          <span>{src.publisher} • {src.document_identifier} ({src.revision})</span>
                          <span className="text-[10px] text-zinc-500 font-mono">
                            SHA: {src.document_hash?.slice(0, 10)}...
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 4. Detailed Inspector Panel */}
              {selectedSource && (
                <div className="p-3 bg-zinc-900/90 border border-sky-800/60 rounded-lg space-y-2 text-xs">
                  <div className="flex items-center justify-between text-sky-400 font-bold">
                    <span>Source Document Inspector</span>
                    <button onClick={() => setSelectedSource(null)} className="text-zinc-500 hover:text-zinc-300">
                      Close Inspector
                    </button>
                  </div>
                  <div className="space-y-1 text-[11px]">
                    <div><span className="text-zinc-500">Document ID:</span> {selectedSource.document_identifier}</div>
                    <div><span className="text-zinc-500">Publisher:</span> {selectedSource.publisher}</div>
                    <div><span className="text-zinc-500">Revision / Version:</span> {selectedSource.revision} (v{selectedSource.version})</div>
                    <div><span className="text-zinc-500">SHA-256 Digest:</span> <span className="text-zinc-300 font-mono text-[10px]">{selectedSource.document_hash || "N/A"}</span></div>
                    <div><span className="text-zinc-500">Status:</span> <span className="text-emerald-400">{selectedSource.status}</span></div>
                    {selectedSource.uri && (
                      <div className="pt-1">
                        <a
                          href={selectedSource.uri}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sky-400 hover:underline flex items-center gap-1 text-[11px]"
                        >
                          <ExternalLink className="w-3 h-3" />
                          View Document Link
                        </a>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {selectedKnowledge && (
                <div className="p-3 bg-zinc-900/90 border border-purple-800/60 rounded-lg space-y-2 text-xs">
                  <div className="flex items-center justify-between text-purple-400 font-bold">
                    <span>Knowledge Record Inspector</span>
                    <button onClick={() => setSelectedKnowledge(null)} className="text-zinc-500 hover:text-zinc-300">
                      Close Inspector
                    </button>
                  </div>
                  <div className="space-y-1 text-[11px]">
                    <div><span className="text-zinc-500">Subject:</span> {selectedKnowledge.subject_identifier}</div>
                    <div><span className="text-zinc-500">Parameter:</span> {selectedKnowledge.parameter}</div>
                    <div><span className="text-zinc-500">Value:</span> {selectedKnowledge.value} {selectedKnowledge.unit || ""}</div>
                    <div><span className="text-zinc-500">Status:</span> {selectedKnowledge.status}</div>
                    <div>
                      <span className="text-zinc-500">Conditions:</span>{" "}
                      <pre className="text-[10px] text-zinc-300 inline">
                        {JSON.stringify(selectedKnowledge.conditions)}
                      </pre>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-zinc-800 flex justify-end bg-zinc-900/60">
          <Button size="sm" onClick={onClose} className="h-7 text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-200">
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
