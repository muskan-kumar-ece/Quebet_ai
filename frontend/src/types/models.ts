export type PlanType = "free" | "plus" | "pro" | "team" | "enterprise";

export interface ModelOption {
  model_id: string;
  display_name: string;
  provider: string;
  is_vision_capable: boolean;
  is_default?: boolean;
  badge?: string;
}

export interface ModelListResponse {
  user_plan: PlanType;
  active_model: string;
  models: ModelOption[];
  can_switch_models: boolean;
  daily_limit: number;
  daily_used: number;
}
