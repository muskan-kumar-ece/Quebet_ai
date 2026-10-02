"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "@/lib/api";

export function StatusIndicator() {
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30000,
  });

  const isHealthy = !isError && data?.success && data?.data?.status === "healthy";
  const isDegraded = !isError && data?.success && data?.data?.status === "degraded";

  return (
    <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-xs">
      <span className="relative flex h-2 w-2">
        {isHealthy && (
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
        )}
        <span
          className={`relative inline-flex rounded-full h-2 w-2 ${
            isHealthy
              ? "bg-emerald-500"
              : isDegraded
              ? "bg-amber-500"
              : "bg-red-500"
          }`}
        />
      </span>
      <span className="text-zinc-400 font-mono text-[11px]">
        {isHealthy ? "API ONLINE" : isDegraded ? "API DEGRADED" : "OFFLINE"}
      </span>
    </div>
  );
}
