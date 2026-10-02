import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  return (
    <Card className="border-zinc-800 bg-zinc-900/60 backdrop-blur-xl">
      <CardHeader className="space-y-1 text-center">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo.svg" alt="Quebet AI" className="w-12 h-12 mx-auto mb-2" />
        <CardTitle className="text-xl font-bold tracking-tight">Sign in to QUEBET AI</CardTitle>
        <CardDescription className="text-xs">
          Access the electronics copilot and knowledge graph
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button variant="outline" className="w-full font-medium text-xs py-5 border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
          Continue with Google
        </Button>
        <div className="relative flex items-center justify-center">
          <div className="w-full border-t border-zinc-800" />
          <span className="absolute bg-zinc-900 px-2 text-[10px] text-zinc-500 uppercase tracking-wider font-mono">
            or email
          </span>
        </div>
        <div className="space-y-2">
          <input
            type="email"
            placeholder="engineer@company.com"
            className="w-full h-9 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-1 text-xs text-white placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-accent-analysis"
          />
          <input
            type="password"
            placeholder="••••••••"
            className="w-full h-9 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-1 text-xs text-white placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-accent-analysis"
          />
        </div>
        <Button className="w-full bg-accent-analysis hover:opacity-90 text-white font-medium text-xs">
          Sign In
        </Button>
        <div className="text-center text-[11px] text-zinc-500">
          New to Quebet?{" "}
          <Link href="/login" className="text-accent-analysis hover:underline">
            Create an account
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
