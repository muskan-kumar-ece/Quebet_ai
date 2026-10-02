import React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GitFork, Save } from "lucide-react";

const ROUTING_MATRIX = [
  {
    task: "Project Builder (Schematics & Netlist)",
    free: "DeepSeek V3",
    plus: "GPT-4o Mini",
    pro: "Claude Sonnet 4",
    enterprise: "Claude Sonnet 4 / Custom",
  },
  {
    task: "Hardware Risk Score Engine",
    free: "DeepSeek V3",
    plus: "Gemini 2.0 Flash",
    pro: "Claude Sonnet 4",
    enterprise: "Claude Sonnet 4",
  },
  {
    task: "Datasheet Simplifier & Text Extraction",
    free: "DeepSeek V3",
    plus: "GPT-4o Mini",
    pro: "GPT-4o",
    enterprise: "GPT-4o",
  },
  {
    task: "Thermal & EMI Static Analysis",
    free: "DeepSeek V3",
    plus: "GPT-4o Mini",
    pro: "Claude Sonnet 4",
    enterprise: "Claude Sonnet 4",
  },
  {
    task: "Debug Wizard (Conversational)",
    free: "DeepSeek V3",
    plus: "Gemini 2.0 Flash",
    pro: "GPT-4o",
    enterprise: "GPT-4o",
  },
  {
    task: "Component Scanner (Vision OCR)",
    free: "❌ Blocked",
    plus: "GPT-4o Mini (Vision)",
    pro: "GPT-4o (Vision)",
    enterprise: "GPT-4o (Vision)",
  },
  {
    task: "PCB Defect Inspection (Vision)",
    free: "❌ Blocked",
    plus: "GPT-4o Mini (Vision)",
    pro: "GPT-4o (Vision)",
    enterprise: "GPT-4o (Vision)",
  },
  {
    task: "Learning Engine & AI Tutor",
    free: "DeepSeek V3",
    plus: "Gemini 2.0 Flash",
    pro: "Claude Sonnet 4",
    enterprise: "Claude Sonnet 4",
  },
];

export default function AdminRoutingPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Plan Routing Matrix
          </h1>
          <p className="text-xs text-zinc-500">
            Map subscription tiers and hardware tasks to primary OpenRouter models. Cached in Redis (5m TTL).
          </p>
        </div>
        <Button size="sm" className="gap-1.5 text-xs bg-purple-600 hover:bg-purple-700 text-white">
          <Save className="w-3.5 h-3.5" />
          <span>Save Changes</span>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Dynamic Task × Tier Mappings</CardTitle>
          <CardDescription>
            Changes save to <code className="text-zinc-400">plan_model_access</code> and take effect immediately without redeploying code.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/40 text-[11px] font-mono text-zinc-400">
                  <th className="py-2.5 px-4 font-medium">Task Type</th>
                  <th className="py-2.5 px-4 font-medium">Free Tier</th>
                  <th className="py-2.5 px-4 font-medium">Plus Tier (₹499)</th>
                  <th className="py-2.5 px-4 font-medium">Pro Tier (₹999)</th>
                  <th className="py-2.5 px-4 font-medium">Enterprise</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60 font-mono">
                {ROUTING_MATRIX.map((row) => (
                  <tr key={row.task} className="hover:bg-zinc-900/30 transition-colors">
                    <td className="py-3 px-4 font-sans text-white font-medium">
                      {row.task}
                    </td>
                    <td className="py-3 px-4 text-zinc-400">
                      {row.free}
                    </td>
                    <td className="py-3 px-4 text-blue-400">
                      {row.plus}
                    </td>
                    <td className="py-3 px-4 text-purple-400">
                      {row.pro}
                    </td>
                    <td className="py-3 px-4 text-emerald-400">
                      {row.enterprise}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
