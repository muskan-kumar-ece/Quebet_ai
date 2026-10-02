import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface KPICardProps {
  title: string;
  value: string | number;
  change?: string;
  changeType?: "positive" | "negative" | "neutral";
  subtitle?: string;
}

export function KPICard({
  title,
  value,
  change,
  changeType = "neutral",
  subtitle,
}: KPICardProps) {
  return (
    <Card className="hover:border-zinc-700 transition-colors">
      <CardHeader className="pb-1">
        <CardTitle className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-xl font-bold font-mono tracking-tight text-white">
          {value}
        </div>
        {(change || subtitle) && (
          <div className="flex items-center gap-1.5 mt-1 text-[11px]">
            {change && (
              <span
                className={`font-mono font-medium ${
                  changeType === "positive"
                    ? "text-emerald-400"
                    : changeType === "negative"
                    ? "text-red-400"
                    : "text-zinc-500"
                }`}
              >
                {change}
              </span>
            )}
            {subtitle && <span className="text-zinc-500">{subtitle}</span>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
