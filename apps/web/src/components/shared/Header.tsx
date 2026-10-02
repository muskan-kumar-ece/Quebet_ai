"use client";

import Link from "next/link";
import { ModelSelector } from "@/components/shared/ModelSelector";
import { StatusIndicator } from "@/components/shared/StatusIndicator";

export function Header() {
  return (
    <header className="sticky top-0 z-40 w-full h-14 border-b border-border/60 bg-background/80 backdrop-blur-md px-4 lg:px-6 flex items-center justify-between">
      {/* Brand logo & mobile trigger */}
      <div className="flex items-center gap-3">
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg overflow-hidden border border-zinc-800 p-0.5 group-hover:border-zinc-700 transition-colors">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/logo.svg" alt="Quebet AI" className="w-full h-full" />
          </div>
          <div className="flex flex-col">
            <span className="font-semibold tracking-tight text-sm text-white flex items-center gap-1.5">
              QUEBET <span className="text-accent-analysis">AI</span>
              <span className="text-[10px] font-mono px-1 py-0.2 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                v0.1
              </span>
            </span>
          </div>
        </Link>
      </div>

      {/* Center / Right controls */}
      <div className="flex items-center gap-3">
        <StatusIndicator />
        <ModelSelector />
        <div className="w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-xs font-semibold text-zinc-300">
          Q
        </div>
      </div>
    </header>
  );
}
