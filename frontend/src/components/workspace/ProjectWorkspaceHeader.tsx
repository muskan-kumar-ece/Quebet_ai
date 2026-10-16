"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cpu,
  Factory,
  GitBranch,
  HelpCircle,
  History,
  Layers,
  Network,
  Package,
  ShieldAlert,
  ShieldCheck,
  XCircle,
  X,
  Zap,
  FileText,
  ChevronRight,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api";
import {
  DomainInventoryItem,
  DomainStatus,
  ProjectActivityItem,
  ProjectActivityTimelineResponse,
  ProjectRevisionLineageResponse,
  ProjectWorkspaceStateResponse,
} from "./types";

interface ProjectWorkspaceHeaderProps {
  projectId: string;
  projectName?: string;
  onNavigateTab?: (tabName: string) => void;
}

const DOMAIN_ICONS: Record<string, React.ElementType> = {
  schematic: Cpu,
  pcb: Layers,
  bom: Package,
  simulation: Zap,
  manufacturing: Factory,
  requirements: FileText,
  design_review: ShieldCheck,
  cross_domain: Network,
};

const STATUS_CONFIG: Record<
  DomainStatus,
  { label: string; badgeClass: string; icon: React.ElementType }
> = {
  CONFIGURED: {
    label: "CONFIGURED",
    badgeClass: "text-emerald-400 border-emerald-800 bg-emerald-950/40",
    icon: CheckCircle2,
  },
  INCOMPLETE: {
    label: "INCOMPLETE",
    badgeClass: "text-amber-400 border-amber-800 bg-amber-950/40",
    icon: AlertTriangle,
  },
  STALE: {
    label: "STALE",
    badgeClass: "text-orange-400 border-orange-800 bg-orange-950/40",
    icon: Clock,
  },
  FAILING_RULES: {
    label: "FAILING",
    badgeClass: "text-red-400 border-red-800 bg-red-950/40",
    icon: XCircle,
  },
  MISSING: {
    label: "MISSING",
    badgeClass: "text-zinc-500 border-zinc-800 bg-zinc-900/50",
    icon: HelpCircle,
  },
  UNKNOWN: {
    label: "UNKNOWN",
    badgeClass: "text-purple-400 border-purple-800 bg-purple-950/40",
    icon: ShieldAlert,
  },
};

export const ProjectWorkspaceHeader: React.FC<ProjectWorkspaceHeaderProps> = ({
  projectId,
  projectName,
  onNavigateTab,
}) => {
  const [isLineageOpen, setIsLineageOpen] = useState(false);
  const [isTimelineOpen, setIsTimelineOpen] = useState(false);
  const [selectedDomain, setSelectedDomain] = useState<DomainInventoryItem | null>(null);

  // 1. Fetch Workspace State
  const { data: workspaceState, refetch: refetchState } = useQuery<ProjectWorkspaceStateResponse>({
    queryKey: ["project-workspace-state", projectId],
    queryFn: async () => {
      const res = await apiClient.get(`/projects/${projectId}/workspace/state`);
      return res.data?.data;
    },
    refetchInterval: 30000,
  });

  // 2. Fetch Revision Lineage
  const { data: lineageData } = useQuery<ProjectRevisionLineageResponse>({
    queryKey: ["project-revision-lineage", projectId],
    queryFn: async () => {
      const res = await apiClient.get(`/projects/${projectId}/workspace/revisions`);
      return res.data?.data;
    },
    enabled: isLineageOpen,
  });

  // 3. Fetch Activity Timeline
  const { data: timelineData } = useQuery<ProjectActivityTimelineResponse>({
    queryKey: ["project-activity-timeline", projectId],
    queryFn: async () => {
      const res = await apiClient.get(`/projects/${projectId}/workspace/activity?limit=50`);
      return res.data?.data;
    },
    enabled: isTimelineOpen,
  });

  const domains = workspaceState?.domains || [];
  const cdvSummary = workspaceState?.cross_domain_validation;
  const isStale = cdvSummary?.is_stale || domains.some((d) => d.status === "STALE");

  return (
    <div className="w-full bg-zinc-950 border-b border-zinc-800 text-zinc-200">
      {/* Staleness Alert Banner */}
      {isStale && (
        <div className="bg-orange-950/70 border-b border-orange-800/80 px-4 py-1.5 flex items-center justify-between text-xs text-orange-200">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-orange-400 shrink-0" />
            <span className="font-semibold uppercase tracking-wider text-[11px]">
              Revision Staleness Detected:
            </span>
            <span className="text-orange-300">
              {cdvSummary?.staleness_reasons?.[0] ||
                "One or more engineering artifacts target an older circuit revision. Re-validation required."}
            </span>
          </div>
          {onNavigateTab && (
            <Button
              size="sm"
              variant="outline"
              className="h-6 px-2 text-[11px] border-orange-700 bg-orange-900/40 hover:bg-orange-800/60 text-orange-200"
              onClick={() => onNavigateTab("xdomain")}
            >
              Inspect Validation
            </Button>
          )}
        </div>
      )}

      {/* Main Workspace Telemetry Bar */}
      <div className="px-4 py-2 flex flex-wrap items-center justify-between gap-3 bg-zinc-900/40">
        {/* Left: Domain Posture Grid */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider mr-1">
            Domains:
          </span>
          {domains.map((dom) => {
            const config = STATUS_CONFIG[dom.status] || STATUS_CONFIG.UNKNOWN;
            const Icon = DOMAIN_ICONS[dom.domain_name] || Cpu;
            const StatusIcon = config.icon;

            return (
              <button
                key={dom.domain_name}
                onClick={() => setSelectedDomain(selectedDomain?.domain_name === dom.domain_name ? null : dom)}
                className={`flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-mono border transition-all ${
                  config.badgeClass
                } ${
                  selectedDomain?.domain_name === dom.domain_name
                    ? "ring-1 ring-sky-400 ring-offset-1 ring-offset-zinc-950"
                    : "hover:opacity-90"
                }`}
                title={`${dom.display_name}: ${dom.status_reason}`}
              >
                <Icon className="w-3 h-3 shrink-0" />
                <span className="font-medium">{dom.display_name}</span>
                <span className="text-[10px] opacity-75">({dom.entity_count})</span>
                <StatusIcon className="w-3 h-3 ml-0.5" />
              </button>
            );
          })}
        </div>

        {/* Right: Lineage, Activity, and Workspace Digest Controls */}
        <div className="flex items-center gap-2 text-xs">
          {workspaceState?.workspace_digest && (
            <div
              className="hidden lg:flex items-center gap-1 text-[10px] font-mono text-zinc-400 bg-zinc-950 px-2 py-1 rounded border border-zinc-800"
              title={`Canonical Workspace SHA-256 Digest: ${workspaceState.workspace_digest}`}
            >
              <span className="text-zinc-500">Digest:</span>
              <span className="text-sky-400">{workspaceState.workspace_digest.slice(0, 8)}…</span>
            </div>
          )}

          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs border-zinc-700 bg-zinc-800/80 hover:bg-zinc-700 text-zinc-200 flex items-center gap-1.5 font-mono"
            onClick={() => {
              setIsLineageOpen(true);
              setIsTimelineOpen(false);
            }}
          >
            <GitBranch className="w-3.5 h-3.5 text-purple-400" />
            <span>Revisions</span>
            {workspaceState?.active_circuit_version && (
              <span className="text-purple-300 font-semibold">
                v{workspaceState.active_circuit_version}
              </span>
            )}
          </Button>

          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs border-zinc-700 bg-zinc-800/80 hover:bg-zinc-700 text-zinc-200 flex items-center gap-1.5 font-mono"
            onClick={() => {
              setIsTimelineOpen(true);
              setIsLineageOpen(false);
            }}
          >
            <History className="w-3.5 h-3.5 text-sky-400" />
            <span>Activity</span>
          </Button>

          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0 text-zinc-400 hover:text-zinc-200"
            onClick={() => refetchState()}
            title="Refresh workspace telemetry"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Selected Domain Posture Details Drawer */}
      {selectedDomain && (
        <div className="bg-zinc-900/90 border-t border-zinc-800 px-4 py-2.5 flex items-center justify-between text-xs">
          <div className="flex items-center gap-3">
            <span className="font-semibold text-zinc-100 font-mono">
              {selectedDomain.display_name}:
            </span>
            <Badge
              variant="outline"
              className={`text-[10px] font-mono ${
                STATUS_CONFIG[selectedDomain.status]?.badgeClass || ""
              }`}
            >
              {selectedDomain.status}
            </Badge>
            <span className="text-zinc-300">{selectedDomain.status_reason}</span>
            {selectedDomain.latest_revision !== null && (
              <span className="text-zinc-500 font-mono">
                Latest Revision: v{selectedDomain.latest_revision}
              </span>
            )}
          </div>
          <button
            onClick={() => setSelectedDomain(null)}
            className="text-zinc-400 hover:text-zinc-200 p-1"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Revision Lineage Modal / Drawer */}
      {isLineageOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex justify-end">
          <div className="w-full max-w-xl bg-zinc-900 border-l border-zinc-800 h-full flex flex-col p-6 overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <GitBranch className="w-5 h-5 text-purple-400" />
                <h2 className="text-base font-semibold text-zinc-100">
                  Revision Lineage & Entity Bindings
                </h2>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => setIsLineageOpen(false)}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>

            <p className="text-xs text-zinc-400 mt-2">
              Cross-domain engineering lineage maps physical layouts, procurement BOMs, simulations,
              DFM runs, and design reviews strictly to their declared schematic circuit revisions.
            </p>

            {/* Circuit Revisions */}
            <div className="mt-6 space-y-6">
              {lineageData?.circuit_revisions?.map((rev) => (
                <div
                  key={rev.circuit_id}
                  className={`p-4 rounded-lg border ${
                    rev.is_current
                      ? "bg-purple-950/20 border-purple-800"
                      : "bg-zinc-950 border-zinc-800"
                  }`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-sm text-purple-300">
                        Circuit Revision v{rev.circuit_version}
                      </span>
                      {rev.is_current && (
                        <Badge className="bg-purple-900/60 text-purple-200 text-[10px] uppercase border-purple-700">
                          Active Revision
                        </Badge>
                      )}
                      <Badge
                        variant="outline"
                        className="text-[10px] font-mono text-zinc-400 border-zinc-700"
                      >
                        {rev.validation_status}
                      </Badge>
                    </div>
                    <span className="text-[11px] text-zinc-500 font-mono">
                      {new Date(rev.created_at).toLocaleDateString()}
                    </span>
                  </div>

                  {/* Bound Artifacts */}
                  <div className="space-y-2 text-xs">
                    {/* PCB Boards */}
                    <div className="flex items-start gap-2">
                      <Layers className="w-3.5 h-3.5 text-purple-400 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold text-zinc-300">PCB Boards: </span>
                        {rev.boards.length === 0 ? (
                          <span className="text-zinc-500 italic">None bound</span>
                        ) : (
                          rev.boards.map((b) => (
                            <span
                              key={b.entity_id}
                              className="inline-block mr-2 text-zinc-300 font-mono"
                            >
                              {b.name_or_type} (v{b.entity_version}, {b.status})
                            </span>
                          ))
                        )}
                      </div>
                    </div>

                    {/* BOMs */}
                    <div className="flex items-start gap-2">
                      <Package className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold text-zinc-300">BOMs: </span>
                        {rev.boms.length === 0 ? (
                          <span className="text-zinc-500 italic">None bound</span>
                        ) : (
                          rev.boms.map((bom) => (
                            <span
                              key={bom.entity_id}
                              className="inline-block mr-2 text-zinc-300 font-mono"
                            >
                              {bom.name_or_type} (v{bom.entity_version}, {bom.status})
                            </span>
                          ))
                        )}
                      </div>
                    </div>

                    {/* Simulations */}
                    <div className="flex items-start gap-2">
                      <Zap className="w-3.5 h-3.5 text-yellow-400 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold text-zinc-300">Simulations: </span>
                        {rev.simulations.length === 0 ? (
                          <span className="text-zinc-500 italic">None recorded</span>
                        ) : (
                          rev.simulations.map((s) => (
                            <span
                              key={s.entity_id}
                              className="inline-block mr-2 text-zinc-300 font-mono"
                            >
                              {s.name_or_type} ({s.status})
                            </span>
                          ))
                        )}
                      </div>
                    </div>

                    {/* DFM */}
                    <div className="flex items-start gap-2">
                      <Factory className="w-3.5 h-3.5 text-orange-400 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold text-zinc-300">DFM Analyses: </span>
                        {rev.manufacturing_analyses.length === 0 ? (
                          <span className="text-zinc-500 italic">None recorded</span>
                        ) : (
                          rev.manufacturing_analyses.map((m) => (
                            <span
                              key={m.entity_id}
                              className="inline-block mr-2 text-zinc-300 font-mono"
                            >
                              {m.name_or_type} ({m.status})
                            </span>
                          ))
                        )}
                      </div>
                    </div>

                    {/* Reviews */}
                    <div className="flex items-start gap-2">
                      <ShieldCheck className="w-3.5 h-3.5 text-teal-400 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold text-zinc-300">Design Reviews: </span>
                        {rev.design_reviews.length === 0 ? (
                          <span className="text-zinc-500 italic">None recorded</span>
                        ) : (
                          rev.design_reviews.map((r) => (
                            <span
                              key={r.entity_id}
                              className="inline-block mr-2 text-zinc-300 font-mono"
                            >
                              {r.name_or_type} ({r.status})
                            </span>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}

              {/* Unbound Entities */}
              {lineageData?.unbound_entities && lineageData.unbound_entities.length > 0 && (
                <div className="p-4 rounded-lg border border-amber-800 bg-amber-950/20">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                    <span className="font-semibold text-sm text-amber-200">
                      Unbound / Orphan Engineering Entities ({lineageData.unbound_entities.length})
                    </span>
                  </div>
                  <p className="text-xs text-amber-300/80 mb-3">
                    These entities reference unknown or non-existent circuit revisions.
                  </p>
                  <div className="space-y-1.5 font-mono text-xs">
                    {lineageData.unbound_entities.map((u) => (
                      <div
                        key={u.entity_id}
                        className="p-2 rounded bg-zinc-950 border border-zinc-800 flex items-center justify-between"
                      >
                        <span>
                          [{u.entity_type}] {u.name_or_type}
                        </span>
                        <span className="text-amber-400 text-[11px]">
                          Target rev: {u.bound_circuit_version ?? "None"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Activity Timeline Modal / Drawer */}
      {isTimelineOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex justify-end">
          <div className="w-full max-w-xl bg-zinc-900 border-l border-zinc-800 h-full flex flex-col p-6 overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <History className="w-5 h-5 text-sky-400" />
                <h2 className="text-base font-semibold text-zinc-100">Project Activity Timeline</h2>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => setIsTimelineOpen(false)}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>

            <p className="text-xs text-zinc-400 mt-2">
              Chronological history reconstructed across all persisted engineering domain records
              with deterministic ordering.
            </p>

            <div className="mt-6 space-y-4">
              {timelineData?.events?.map((ev) => (
                <div
                  key={ev.event_id}
                  className="p-3 rounded-lg border border-zinc-800 bg-zinc-950 flex flex-col gap-1.5"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className="text-[10px] font-mono text-sky-400 border-sky-800 bg-sky-950/40 uppercase"
                      >
                        {ev.category}
                      </Badge>
                      <span className="text-xs font-semibold text-zinc-200">{ev.entity_name}</span>
                      {ev.revision_or_version !== null && (
                        <span className="text-[10px] text-zinc-500 font-mono">
                          v{ev.revision_or_version}
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-zinc-500 font-mono">
                      {new Date(ev.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-300">{ev.summary}</p>
                </div>
              ))}

              {(!timelineData?.events || timelineData.events.length === 0) && (
                <div className="text-center py-12 text-zinc-500 text-xs font-mono">
                  No activity events recorded yet.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
