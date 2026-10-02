"use client";

import { useEffect, useState } from "react";
import { Plus, Check, X, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetchAdminModels, toggleModelActive } from "@/lib/api";

interface ModelItem {
  id: string;
  model_id: string;
  display_name: string;
  provider: string;
  is_vision_capable: boolean;
  is_active: boolean;
  cost_per_1k_input: number;
  cost_per_1k_output: number;
  max_context_tokens: number;
  notes?: string;
}

export default function AdminModelsPage() {
  const [models, setModels] = useState<ModelItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAdminModels()
      .then((res) => {
        if (res?.success && res?.data) {
          setModels(res.data);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const handleToggle = async (modelId: string, currentActive: boolean) => {
    try {
      await toggleModelActive(modelId, !currentActive);
      setModels((prev) =>
        prev.map((m) =>
          m.model_id === modelId ? { ...m, is_active: !currentActive } : m
        )
      );
    } catch {
      // Optimistic revert or alert
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            OpenRouter Model Catalog
          </h1>
          <p className="text-xs text-zinc-500">
            Registered AI models available for subscription tier routing and inference failovers.
          </p>
        </div>
        <Button size="sm" className="gap-1.5 text-xs bg-purple-600 hover:bg-purple-700 text-white">
          <Plus className="w-3.5 h-3.5" />
          <span>Add Model</span>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Registered Models ({models.length})</CardTitle>
              <CardDescription>
                Live configuration from PostgreSQL <code className="text-zinc-400">model_configs</code> table
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/40 text-[11px] font-mono text-zinc-400">
                  <th className="py-2.5 px-4 font-medium">Model</th>
                  <th className="py-2.5 px-4 font-medium">OpenRouter ID</th>
                  <th className="py-2.5 px-4 font-medium">Provider</th>
                  <th className="py-2.5 px-4 font-medium">Vision</th>
                  <th className="py-2.5 px-4 font-medium">Input / 1k</th>
                  <th className="py-2.5 px-4 font-medium">Output / 1k</th>
                  <th className="py-2.5 px-4 font-medium">Context</th>
                  <th className="py-2.5 px-4 font-medium text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60 font-mono">
                {models.map((model) => (
                  <tr
                    key={model.model_id}
                    className="hover:bg-zinc-900/30 transition-colors"
                  >
                    <td className="py-3 px-4 font-sans font-medium text-white">
                      {model.display_name}
                    </td>
                    <td className="py-3 px-4 text-zinc-400 text-[11px]">
                      {model.model_id}
                    </td>
                    <td className="py-3 px-4 uppercase text-[10px] text-zinc-400">
                      {model.provider}
                    </td>
                    <td className="py-3 px-4">
                      {model.is_vision_capable ? (
                        <span className="text-emerald-400 text-[10px] font-sans">Yes</span>
                      ) : (
                        <span className="text-zinc-600 text-[10px] font-sans">No</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-zinc-300">
                      ${model.cost_per_1k_input.toFixed(5)}
                    </td>
                    <td className="py-3 px-4 text-zinc-300">
                      ${model.cost_per_1k_output.toFixed(5)}
                    </td>
                    <td className="py-3 px-4 text-zinc-400">
                      {(model.max_context_tokens / 1000).toFixed(0)}k
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleToggle(model.model_id, model.is_active)}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-sans font-medium transition-colors ${
                          model.is_active
                            ? "bg-emerald-950/60 text-emerald-400 border border-emerald-900/50 hover:bg-emerald-900/40"
                            : "bg-zinc-900 text-zinc-500 border border-zinc-800 hover:text-zinc-300"
                        }`}
                      >
                        {model.is_active ? "Active" : "Disabled"}
                      </button>
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
