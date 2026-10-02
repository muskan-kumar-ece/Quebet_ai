"use client";

import Link from "next/link";
import { ShieldCheck, ExternalLink, Terminal } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function AdminHeader() {
  return (
    <header className="sticky top-0 z-40 w-full h-12 border-b border-zinc-800 bg-zinc-950 px-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <Link href="/" className="flex items-center gap-2">
          <span className="font-bold tracking-tight text-white flex items-center gap-1.5">
            QUEBET <span className="text-purple-400">ADMIN</span>
          </span>
          <Badge variant="outline" className="border-purple-800/50 bg-purple-950/20 text-purple-300">
            INTERNAL PORTAL
          </Badge>
        </Link>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-[11px] font-mono text-zinc-400">
          <Terminal className="w-3.5 h-3.5 text-emerald-400" />
          <span>OPENROUTER GATEWAY: LIVE</span>
        </div>
        <a
          href="http://localhost:3000"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 text-[11px] text-zinc-400 hover:text-white transition-colors"
        >
          <span>Open Client App</span>
          <ExternalLink className="w-3 h-3" />
        </a>
        <div className="w-7 h-7 rounded-full bg-purple-950 border border-purple-800 flex items-center justify-center text-[10px] font-bold text-purple-300">
          SU
        </div>
      </div>
    </header>
  );
}
