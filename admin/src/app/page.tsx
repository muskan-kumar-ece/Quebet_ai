import React from "react";
import { KPICard } from "@/components/shared/KPICard";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RefreshCw, ArrowUpRight, Zap, Shield, Sparkles } from "lucide-react";

export default function AdminOverviewPage() {
  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Operations Console
            <Badge variant="outline" className="text-[10px] text-zinc-400 border-zinc-800">
              PRODUCTION CLUSTER
            </Badge>
          </h1>
          <p className="text-xs text-zinc-500">
            Real-time telemetry, model economics, and subscription usage.
          </p>
        </div>
        <Button variant="outline" size="sm" className="gap-1.5 text-xs text-zinc-400">
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh Metrics</span>
        </Button>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <KPICard
          title="Total Registered Users"
          value="1,482"
          change="+18.4%"
          changeType="positive"
          subtitle="vs last month"
        />
        <KPICard
          title="Token Consumption (30d)"
          value="14.2M"
          change="+32.1%"
          changeType="neutral"
          subtitle="tokens routed"
        />
        <KPICard
          title="OpenRouter Cost (30d)"
          value="$38.45"
          change="₹3,180"
          changeType="positive"
          subtitle="est. upstream bill"
        />
        <KPICard
          title="Avg Inference Latency"
          value="640ms"
          change="-45ms"
          changeType="positive"
          subtitle="P95 TTFT"
        />
      </div>

      {/* Two Column Layout: Plan Distribution & Model Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Tier Distribution */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Plan Tier Breakdown</CardTitle>
                <CardDescription>Active subscriptions and daily quota utilization</CardDescription>
              </div>
              <Badge variant="outline">UPDATED 1M AGO</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              { plan: "Free Tier", users: 1120, pct: "75.5%", model: "DeepSeek V3", quota: "10 gen/day", color: "bg-zinc-600" },
              { plan: "Plus Tier (₹499)", users: 284, pct: "19.1%", model: "Gemini 2.0 Flash / GPT-4o-mini", quota: "50 gen/day", color: "bg-blue-500" },
              { plan: "Pro Tier (₹999)", users: 72, pct: "4.8%", model: "Claude Sonnet 4 / GPT-4o", quota: "200 gen/day", color: "bg-purple-500" },
              { plan: "Enterprise", users: 6, pct: "0.6%", model: "Custom / Dedicated", quota: "Unlimited", color: "bg-emerald-500" },
            ].map((tier) => (
              <div key={tier.plan} className="p-3 rounded-lg border border-zinc-800/80 bg-zinc-900/30 flex items-center justify-between">
                <div className="space-y-0.5">
                  <div className="font-medium text-xs text-white flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${tier.color}`} />
                    <span>{tier.plan}</span>
                    <span className="text-zinc-500 font-normal">({tier.users} users)</span>
                  </div>
                  <div className="text-[11px] text-zinc-400 font-mono">
                    Default: {tier.model}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-mono font-bold text-white">{tier.pct}</div>
                  <div className="text-[10px] text-zinc-500">{tier.quota}</div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Model Circuit Breaker Status */}
        <Card>
          <CardHeader>
            <CardTitle>Circuit Breaker Status</CardTitle>
            <CardDescription>Real-time upstream health per model</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {[
              { name: "DeepSeek V3", status: "CLOSED (Healthy)", errorRate: "0.2%", ping: "420ms" },
              { name: "Gemini 2.0 Flash", status: "CLOSED (Healthy)", errorRate: "0.0%", ping: "380ms" },
              { name: "GPT-4o Mini", status: "CLOSED (Healthy)", errorRate: "0.1%", ping: "510ms" },
              { name: "Claude Sonnet 4", status: "CLOSED (Healthy)", errorRate: "0.4%", ping: "890ms" },
              { name: "GPT-4o", status: "CLOSED (Healthy)", errorRate: "0.3%", ping: "780ms" },
            ].map((model) => (
              <div key={model.name} className="flex items-center justify-between py-1.5 border-b border-zinc-900 text-xs">
                <div>
                  <div className="font-mono text-zinc-300">{model.name}</div>
                  <div className="text-[10px] text-emerald-400 font-mono">{model.status}</div>
                </div>
                <div className="text-right font-mono text-[11px] text-zinc-400">
                  <div>{model.ping}</div>
                  <div className="text-[10px] text-zinc-600">Err: {model.errorRate}</div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
