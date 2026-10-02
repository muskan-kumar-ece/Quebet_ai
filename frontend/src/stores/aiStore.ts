import { create } from "zustand";
import { ModelOption, PlanType } from "@/types/models";

interface AIState {
  userPlan: PlanType;
  activeModel: string;
  availableModels: ModelOption[];
  canSwitchModels: boolean;
  dailyLimit: number;
  dailyUsed: number;
  setUserPlan: (plan: PlanType) => void;
  setActiveModel: (modelId: string) => void;
  setAvailableModels: (models: ModelOption[], active: string, canSwitch: boolean) => void;
}

export const useAIStore = create<AIState>((set) => ({
  userPlan: "free",
  activeModel: "deepseek/deepseek-chat-v3-0324",
  availableModels: [
    {
      model_id: "deepseek/deepseek-chat-v3-0324",
      display_name: "DeepSeek V3",
      provider: "deepseek",
      is_vision_capable: false,
      badge: "DEFAULT",
    },
  ],
  canSwitchModels: false,
  dailyLimit: 10,
  dailyUsed: 0,
  setUserPlan: (plan) => set({ userPlan: plan }),
  setActiveModel: (activeModel) => set({ activeModel }),
  setAvailableModels: (availableModels, activeModel, canSwitchModels) =>
    set({ availableModels, activeModel, canSwitchModels }),
}));
