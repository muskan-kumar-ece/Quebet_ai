"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Cpu,
  GitFork,
  Gauge,
  Users,
  ScrollText,
  Sliders,
} from "lucide-react";

const NAV_ITEMS = [
  { name: "Executive Overview", href: "/", icon: BarChart3 },
  { name: "Model Catalog", href: "/models", icon: Cpu },
  { name: "Plan Routing Matrix", href: "/routing", icon: GitFork },
  { name: "Rate Limits", href: "/rate-limits", icon: Gauge },
  { name: "User Accounts", href: "/users", icon: Users },
  { name: "AI Audit Logs", href: "/logs", icon: ScrollText },
];

export function AdminSidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 h-[calc(100vh-3rem)] border-r border-zinc-800 bg-zinc-950 p-2.5 flex flex-col justify-between select-none">
      <div className="space-y-3">
        <div className="px-2.5 text-[10px] font-mono tracking-wider text-zinc-500 uppercase">
          Platform Operations
        </div>
        <nav className="space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? "bg-zinc-900 text-white border border-zinc-800 font-semibold"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/50"
                }`}
              >
                <Icon
                  className={`w-3.5 h-3.5 ${
                    isActive ? "text-purple-400" : "text-zinc-500"
                  }`}
                />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="p-2.5 rounded-lg border border-zinc-900 bg-zinc-900/30 text-[11px] text-zinc-500 space-y-1">
        <div className="flex items-center justify-between">
          <span>Backend:</span>
          <span className="font-mono text-emerald-400">Online</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Version:</span>
          <span className="font-mono text-zinc-400">0.1.0</span>
        </div>
      </div>
    </aside>
  );
}
