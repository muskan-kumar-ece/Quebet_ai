import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4 text-center">
      <div className="text-6xl font-bold font-mono tracking-tighter text-zinc-700 mb-2">404</div>
      <h1 className="text-xl font-semibold text-white mb-2">Signal Trace Lost</h1>
      <p className="text-sm text-zinc-400 max-w-sm mb-6">
        The circuit node or page you are probing does not exist or has been disconnected from the bus.
      </p>
      <Button asChild variant="outline">
        <Link href="/">Return to Dashboard</Link>
      </Button>
    </div>
  );
}
