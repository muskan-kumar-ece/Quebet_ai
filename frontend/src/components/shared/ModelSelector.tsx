"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Sparkles, Lock } from "lucide-react";
import { useAIStore } from "@/stores/aiStore";
import { Badge } from "@/components/ui/badge";
import { fetchModels } from "@/lib/api";

export function ModelSelector() {
  const {
    userPlan,
    activeModel,
    availableModels,
    canSwitchModels,
    setActiveModel,
    setAvailableModels,
  } = useAIStore();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    fetchModels(userPlan)
      .then((res) => {
        if (res?.success && res?.data) {
          setAvailableModels(
            res.data.models,
            res.data.active_model,
            res.data.can_switch_models
          );
        }
      })
      .catch(() => {});
  }, [userPlan, setAvailableModels]);

  const activeOption = availableModels.find((m) => m.model_id === activeModel) || {
    display_name: activeModel.split("/").pop() || activeModel,
    badge: "ACTIVE",
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => canSwitchModels && setIsOpen(!isOpen)}
        disabled={!canSwitchModels}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
          canSwitchModels
            ? "bg-zinc-900 border-zinc-700 hover:border-zinc-500 text-zinc-200 cursor-pointer"
            : "bg-zinc-950 border-zinc-800 text-zinc-400 cursor-default"
        }`}
      >
        <Sparkles className="w-3.5 h-3.5 text-blue-400" />
        <span className="font-mono">{activeOption.display_name}</span>
        <Badge
          variant={
            userPlan === "pro"
              ? "pro"
              : userPlan === "plus"
              ? "plus"
              : "free"
          }
          className="uppercase tracking-wider text-[10px] px-1.5 py-0"
        >
          {userPlan}
        </Badge>
        {canSwitchModels ? (
          <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
        ) : (
          <Lock className="w-3 h-3 text-zinc-600" />
        )}
      </button>

      {isOpen && canSwitchModels && (
        <div className="absolute right-0 mt-2 w-64 rounded-xl border border-zinc-800 bg-zinc-950/95 backdrop-blur-md p-1 shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-100">
          <div className="px-2.5 py-1.5 text-[11px] font-semibold text-zinc-500 uppercase tracking-wider">
            Available Models ({userPlan.toUpperCase()})
          </div>
          <div className="space-y-0.5">
            {availableModels.map((model) => {
              const isSelected = model.model_id === activeModel;
              return (
                <button
                  key={model.model_id}
                  onClick={() => {
                    setActiveModel(model.model_id);
                    setIsOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left text-xs transition-colors ${
                    isSelected
                      ? "bg-zinc-800 text-white font-medium"
                      : "text-zinc-300 hover:bg-zinc-900 hover:text-white"
                  }`}
                >
                  <div>
                    <div className="font-mono text-xs">{model.display_name}</div>
                    <div className="text-[10px] text-zinc-500">{model.provider}</div>
                  </div>
                  {model.badge && (
                    <Badge variant="outline" className="text-[9px] px-1 py-0 border-zinc-700">
                      {model.badge}
                    </Badge>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
