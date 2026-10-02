import React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Save, Gauge } from "lucide-react";

const LIMITS_DATA = [
  {
    plan: "Free Tier",
    rpm: 10,
    daily_generations: 10,
    daily_vision: "None",
    concurrent_jobs: 1,
    badge: "free",
  },
  {
    plan: "Plus Tier (₹499)",
    rpm: 30,
    daily_generations: 50,
    daily_vision: "15 / day",
    concurrent_jobs: 3,
    badge: "plus",
  },
  {
    plan: "Pro Tier (₹999)",
    rpm: 60,
    daily_generations: 200,
    daily_vision: "Unlimited",
    concurrent_jobs: 5,
    badge: "pro",
  },
  {
    plan: "Team Tier (₹4,999)",
    rpm: 60,
    daily_generations: "200 / user",
    daily_vision: "Unlimited",
    concurrent_jobs: 5,
    badge: "pro",
  },
  {
    plan: "Enterprise",
    rpm: 300,
    daily_generations: "Custom / ∞",
    daily_vision: "Unlimited",
    concurrent_jobs: 20,
    badge: "enterprise",
  },
];

export default function AdminRateLimitsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Rate Limit Controls
          </h1>
          <p className="text-xs text-zinc-500">
            Tune Layer 1 (BFF RPM) and Layer 2 (Daily Gen) quotas per tier without redeploying services.
          </p>
        </div>
        <Button size="sm" className="gap-1.5 text-xs bg-purple-600 hover:bg-purple-700 text-white">
          <Save className="w-3.5 h-3.5" />
          <span>Apply Quotas</span>
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {LIMITS_DATA.map((tier) => (
          <Card key={tier.plan} className="border-zinc-800 bg-zinc-900/40">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-bold text-white">{tier.plan}</CardTitle>
                <Badge variant={tier.badge as any}>{tier.badge.toUpperCase()}</Badge>
              </div>
              <CardDescription className="text-[11px]">
                Enforced by Redis sliding window & semaphores
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 pt-2 font-mono text-xs">
              <div className="flex items-center justify-between py-1.5 border-b border-zinc-800/60">
                <span className="text-zinc-400 font-sans">BFF Rate Limit (RPM):</span>
                <span className="text-white font-bold">{tier.rpm} req/min</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-zinc-800/60">
                <span className="text-zinc-400 font-sans">Daily Generations:</span>
                <span className="text-white font-bold">{tier.daily_generations}</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-zinc-800/60">
                <span className="text-zinc-400 font-sans">Vision Quota:</span>
                <span className="text-white font-bold">{tier.daily_vision}</span>
              </div>
              <div className="flex items-center justify-between py-1.5">
                <span className="text-zinc-400 font-sans">Max Concurrent Jobs:</span>
                <span className="text-white font-bold">{tier.concurrent_jobs}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
