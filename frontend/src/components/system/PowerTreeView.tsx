"use client";

import React from "react";
import { Zap, AlertTriangle, CheckCircle2, Sliders, ArrowDownRight, Layers } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EngineeringPowerDomain, EngineeringSubsystem } from "./types";

interface PowerTreeViewProps {
  powerDomains: EngineeringPowerDomain[];
  subsystems: EngineeringSubsystem[];
  onSelectSubsystem?: (id: string) => void;
}

export const PowerTreeView: React.FC<PowerTreeViewProps> = ({
  powerDomains,
  subsystems,
  onSelectSubsystem,
}) => {
  const subById = React.useMemo(() => {
    return new Map(subsystems.map((s) => [s.id, s]));
  }, [subsystems]);

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto overflow-y-auto h-full">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div>
          <h2 className="text-base font-bold text-zinc-100 flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400" />
            System Power Distribution Tree
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Deterministic supply rail hierarchy, regulator topologies, and aggregated load margins.
          </p>
        </div>
        <Badge variant="outline" className="font-mono text-xs border-amber-800 text-amber-300 bg-amber-950/40">
          {powerDomains.length} Power Domains
        </Badge>
      </div>

      {powerDomains.length === 0 ? (
        <Card className="bg-zinc-900/40 border-zinc-800 text-zinc-400 p-8 text-center text-xs">
          No power domains configured for this system. Define voltage domains to track current budgets.
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {powerDomains.map((domain) => {
            const sourceSub = subById.get(domain.source_subsystem_id);
            const regSub = domain.regulator_subsystem_id
              ? subById.get(domain.regulator_subsystem_id)
              : null;
            const meta = domain.metadata || {};
            const estimatedLoad = meta.estimated_load_a ?? 0;
            const capacity = domain.current_capacity_a ?? 0;
            const isOverloaded = capacity > 0 && estimatedLoad > capacity;
            const margin = capacity > 0 ? capacity - estimatedLoad : null;

            return (
              <Card
                key={domain.id}
                className={`bg-zinc-900/60 border transition-all ${
                  isOverloaded
                    ? "border-red-600/80 shadow-red-950/40 shadow-lg"
                    : "border-zinc-800 hover:border-zinc-700"
                }`}
              >
                <CardHeader className="p-4 pb-2 flex flex-row items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-amber-500" />
                    <CardTitle className="text-sm font-mono font-bold text-zinc-200">
                      {domain.name}
                    </CardTitle>
                  </div>
                  <div className="flex items-center gap-1.5 font-mono text-xs font-bold text-amber-400 bg-amber-950/60 px-2 py-0.5 rounded border border-amber-800/80">
                    {domain.nominal_voltage}V Rail
                  </div>
                </CardHeader>
                <CardContent className="p-4 pt-2 space-y-3">
                  {/* Voltage Bounds */}
                  <div className="grid grid-cols-3 gap-2 text-[11px] font-mono bg-zinc-950/50 p-2 rounded border border-zinc-800/80">
                    <div>
                      <span className="text-zinc-500 block">Min V</span>
                      <span className="text-zinc-300 font-bold">{domain.min_voltage ?? "—"}V</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block">Nominal</span>
                      <span className="text-amber-400 font-bold">{domain.nominal_voltage}V</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block">Max V</span>
                      <span className="text-zinc-300 font-bold">{domain.max_voltage ?? "—"}V</span>
                    </div>
                  </div>

                  {/* Sourcing Topology */}
                  <div className="space-y-1.5 text-xs">
                    <div className="flex items-center justify-between text-zinc-400">
                      <span className="text-zinc-500 text-[11px]">Primary Source:</span>
                      <span
                        onClick={() => sourceSub && onSelectSubsystem?.(sourceSub.id)}
                        className="font-medium text-zinc-200 hover:text-sky-400 cursor-pointer underline decoration-dotted"
                      >
                        {sourceSub?.name || "Uncharacterized"}
                      </span>
                    </div>
                    {regSub && (
                      <div className="flex items-center justify-between text-zinc-400">
                        <span className="text-zinc-500 text-[11px] flex items-center gap-1">
                          <ArrowDownRight className="w-3 h-3 text-orange-400" />
                          Regulator:
                        </span>
                        <span
                          onClick={() => onSelectSubsystem?.(regSub.id)}
                          className="font-medium text-orange-300 hover:text-sky-400 cursor-pointer underline decoration-dotted"
                        >
                          {regSub.name}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Current Demand vs Capacity Bar */}
                  <div className="space-y-1 pt-1 border-t border-zinc-800/60">
                    <div className="flex items-center justify-between text-[11px] font-mono">
                      <span className="text-zinc-400">Load: {estimatedLoad}A</span>
                      <span className="text-zinc-400">Capacity: {capacity > 0 ? `${capacity}A` : "Unrated"}</span>
                    </div>
                    {capacity > 0 && (
                      <div className="w-full h-2 rounded-full bg-zinc-800 overflow-hidden">
                        <div
                          className={`h-full transition-all ${
                            isOverloaded ? "bg-red-500" : "bg-emerald-500"
                          }`}
                          style={{ width: `${Math.min((estimatedLoad / capacity) * 100, 100)}%` }}
                        />
                      </div>
                    )}
                    {isOverloaded && (
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-red-400 pt-1">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        <span>Rail overloaded by {Math.abs(margin!).toFixed(2)}A!</span>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};
