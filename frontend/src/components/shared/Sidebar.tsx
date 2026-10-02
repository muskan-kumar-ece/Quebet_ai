"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Cpu,
  ShieldAlert,
  Wrench,
  Layers,
  GraduationCap,
  Network,
  Settings,
  FolderGit2,
  Sliders,
} from "lucide-react";
import { MODULE_NAV_ITEMS } from "@/lib/constants";

const ICON_MAP = {
  Cpu,
  ShieldAlert,
  Wrench,
  Layers,
  GraduationCap,
  Network,
};

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 h-[calc(100vh-3.5rem)] border-r border-border/60 bg-zinc-950 flex flex-col justify-between p-3 select-none">
      {/* Module Navigation */}
      <div className="space-y-4">
        <div>
          <div className="px-3 mb-2 text-[11px] font-mono tracking-wider text-zinc-500 uppercase">
            Engineering Modules
          </div>
          <nav className="space-y-1">
            {MODULE_NAV_ITEMS.map((item) => {
              const Icon = ICON_MAP[item.iconName as keyof typeof ICON_MAP] || Cpu;
              const isActive = pathname.startsWith(item.href);

              return (
                <Link
                  key={item.id}
                  href={item.href}
                  className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all group ${
                    isActive
                      ? "bg-zinc-900 text-white shadow-sm border border-zinc-800"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60"
                  }`}
                >
                  <Icon
                    className={`w-4 h-4 transition-colors ${
                      isActive ? item.accentClass : "text-zinc-500 group-hover:text-zinc-300"
                    }`}
                  />
                  <span className="flex-1 truncate">{item.name}</span>
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      isActive ? item.bgAccentClass : "bg-transparent group-hover:bg-zinc-700"
                    }`}
                  />
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Workspace section */}
        <div>
          <div className="px-3 mb-2 text-[11px] font-mono tracking-wider text-zinc-500 uppercase">
            Workspace
          </div>
          <nav className="space-y-1">
            <Link
              href="/projects"
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60 transition-colors"
            >
              <FolderGit2 className="w-4 h-4 text-zinc-500" />
              <span>Saved Projects</span>
            </Link>
            <Link
              href="/settings"
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60 transition-colors"
            >
              <Settings className="w-4 h-4 text-zinc-500" />
              <span>Settings</span>
            </Link>
          </nav>
        </div>
      </div>

      {/* Admin Quick Link */}
      <div className="pt-3 border-t border-zinc-900">
        <Link
          href="/admin/models"
          className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/40 transition-colors"
        >
          <Sliders className="w-3.5 h-3.5" />
          <span>Admin: Model Catalog</span>
        </Link>
      </div>
    </aside>
  );
}
