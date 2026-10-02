import type { Metadata } from "next";
import { AdminHeader } from "@/components/shared/AdminHeader";
import { AdminSidebar } from "@/components/shared/AdminSidebar";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "QUEBET AI — Admin & Operations Console",
  description: "Internal model routing, tier economics, and platform controls",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background font-sans antialiased text-foreground">
        <AdminHeader />
        <div className="flex overflow-hidden">
          <AdminSidebar />
          <main className="flex-1 overflow-y-auto p-6 bg-zinc-950/40 min-h-[calc(100vh-3rem)]">
            <div className="max-w-6xl mx-auto">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
