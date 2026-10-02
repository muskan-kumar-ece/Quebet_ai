"use client";

import Link from "next/link";
import {
  Cpu,
  ShieldAlert,
  Wrench,
  Layers,
  GraduationCap,
  Network,
  ArrowRight,
  Sparkles,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MODULE_NAV_ITEMS } from "@/lib/constants";
import { useAIStore } from "@/stores/aiStore";

const ICON_MAP = {
  Cpu,
  ShieldAlert,
  Wrench,
  Layers,
  GraduationCap,
  Network,
};

export default function DashboardOverviewPage() {
  const { userPlan, activeModel } = useAIStore();

  return (
    <div className="space-y-8">
      {/* Top Welcome / Hero Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-zinc-800 bg-gradient-to-r from-zinc-950 via-zinc-900 to-zinc-950 p-6 lg:p-8">
        <div className="max-w-2xl space-y-3">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-xs font-mono text-blue-400">
            <Zap className="w-3.5 h-3.5" />
            <span>QUEBET AI COPILOT READY</span>
          </div>
          <h1 className="text-2xl lg:text-3xl font-bold tracking-tight text-white">
            Hardware Engineering Copilot
          </h1>
          <p className="text-sm text-zinc-400">
            Validate schematics, predict thermal & EMI failures, analyze BOM costs with Indian sourcing,
            and inspect PCB defects with multi-model AI reasoning.
          </p>
        </div>

        {/* Quick Prompt Input */}
        <div className="mt-6 max-w-3xl">
          <div className="relative flex items-center">
            <input
              type="text"
              placeholder="e.g. Design a 5V 2A buck converter circuit with ESP32 and USB-C input..."
              className="w-full h-12 pl-4 pr-32 rounded-xl border border-zinc-700 bg-zinc-900/90 text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-accent-analysis/50 focus:border-accent-analysis shadow-lg"
            />
            <Button
              className="absolute right-1.5 h-9 bg-accent-analysis hover:opacity-90 text-white font-medium text-xs px-4 rounded-lg flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Generate</span>
            </Button>
          </div>
          <div className="flex items-center gap-2 mt-2 text-[11px] text-zinc-500">
            <span>Active Model:</span>
            <span className="font-mono text-zinc-400">{activeModel}</span>
            <span>•</span>
            <span>Plan:</span>
            <span className="font-mono uppercase text-zinc-400">{userPlan}</span>
          </div>
        </div>
      </div>

      {/* Module Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-white tracking-tight">
            Engineering Modules
          </h2>
          <span className="text-xs text-zinc-500 font-mono">6 CORE MODULES ACTIVE</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {MODULE_NAV_ITEMS.map((module) => {
            const Icon = ICON_MAP[module.iconName as keyof typeof ICON_MAP] || Cpu;

            return (
              <Card
                key={module.id}
                className="group relative overflow-hidden border-zinc-800/80 bg-zinc-900/40 hover:bg-zinc-900/80 hover:border-zinc-700 transition-all hover:shadow-xl"
              >
                <div
                  className={`absolute top-0 left-0 right-0 h-1 opacity-60 group-hover:opacity-100 transition-opacity ${module.bgAccentClass}`}
                />
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className={`p-2 rounded-lg bg-zinc-950 border border-zinc-800 ${module.accentClass}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <ArrowRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-300 transition-colors transform group-hover:translate-x-0.5" />
                  </div>
                  <CardTitle className="text-base font-semibold text-white mt-3">
                    {module.name}
                  </CardTitle>
                  <CardDescription className="text-xs text-zinc-400 line-clamp-2">
                    {module.description}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button
                    asChild
                    variant="ghost"
                    className="w-full justify-between text-xs font-medium text-zinc-300 hover:text-white p-0 h-auto"
                  >
                    <Link href={module.href}>
                      <span>Open Workspace</span>
                      <span className="text-[11px] font-mono text-zinc-500">→</span>
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Signature Risk Score Feature Callout */}
      <Card className="border-blue-500/20 bg-gradient-to-r from-blue-950/20 via-zinc-900/50 to-zinc-950 p-6 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 text-xs font-mono text-blue-400 font-semibold">
            <ShieldAlert className="w-4 h-4" />
            <span>SIGNATURE ENGINE</span>
          </div>
          <h3 className="text-lg font-bold text-white">Hardware Risk Score Analysis</h3>
          <p className="text-xs text-zinc-400 max-w-xl">
            Evaluate composite failure probability (0–100) combining thermal dissipation calculations,
            high-frequency EMI layout rules, and component quality derating.
          </p>
        </div>
        <Button asChild className="bg-accent-analysis hover:opacity-90 text-white shrink-0 text-xs font-medium">
          <Link href="/analysis/risk-score">Launch Risk Analyzer</Link>
        </Button>
      </Card>
    </div>
  );
}
