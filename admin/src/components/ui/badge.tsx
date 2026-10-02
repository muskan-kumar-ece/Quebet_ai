import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded px-2 py-0.5 text-[10px] font-mono font-semibold transition-colors focus:outline-none",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-zinc-800 bg-zinc-900 text-zinc-300",
        destructive: "border-red-900/40 bg-red-950/40 text-red-400",
        outline: "border-zinc-800 text-zinc-400",
        active: "border-emerald-900/50 bg-emerald-950/40 text-emerald-400",
        inactive: "border-zinc-800 bg-zinc-900/40 text-zinc-500",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
