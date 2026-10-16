"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { FolderGit2, Plus, Cpu, Zap, Radio, Flame, Battery, Wrench, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";

const TYPE_ICONS: Record<string, any> = {
  circuit: Cpu,
  power: Zap,
  embedded: Cpu,
  rf: Radio,
  thermal: Flame,
  battery: Battery,
  general: Wrench,
};

export default function ProjectsDashboardPage() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectDesc, setNewProjectDesc] = useState("");
  const [newProjectType, setNewProjectType] = useState("circuit");

  // Fetch projects from API
  const { data, isLoading, error } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      try {
        const res = await apiClient.get("/projects");
        if (res.data?.success) {
          return res.data.data.projects;
        }
      } catch (err) {
        // Fallback for offline dev
        console.warn("Backend offline, loading default projects.");
      }
      return [
        {
          id: "proj-demo-1",
          name: "5V 2A Regulated Power Supply",
          description: "Dual rail linear regulator circuit with LM7805 and filtering",
          project_type: "power",
          status: "active",
          created_at: new Date().toISOString(),
        },
        {
          id: "proj-demo-2",
          name: "ESP32 Sensor Node Baseboard",
          description: "Low-power IoT controller with USB-C and battery charger",
          project_type: "embedded",
          status: "active",
          created_at: new Date().toISOString(),
        },
      ];
    },
  });

  const createMutation = useMutation({
    mutationFn: async (payload: { name: string; description: string; project_type: string }) => {
      const res = await apiClient.post("/projects", payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setShowCreateModal(false);
      setNewProjectName("");
      setNewProjectDesc("");
    },
    onError: () => {
      // Offline fallback: close and inform
      setShowCreateModal(false);
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    createMutation.mutate({
      name: newProjectName,
      description: newProjectDesc,
      project_type: newProjectType,
    });
  };

  const projects = data || [];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <FolderGit2 className="w-5 h-5 text-blue-400" />
            <h1 className="text-xl font-bold tracking-tight text-white">Engineering Projects</h1>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Manage your hardware design projects, circuits, and electrical specifications.
          </p>
        </div>
        <Button
          onClick={() => setShowCreateModal(true)}
          className="bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs flex items-center gap-1.5 self-start"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Project</span>
        </Button>
      </div>

      {/* Create Project Modal Dialog */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <Card className="w-full max-w-md border-zinc-800 bg-zinc-950 text-white shadow-2xl">
            <CardHeader className="pb-3 border-b border-zinc-800">
              <CardTitle className="text-base font-bold">Create Engineering Project</CardTitle>
              <CardDescription className="text-xs text-zinc-400">
                Establish an isolated workspace for circuit, PCB, or power system design.
              </CardDescription>
            </CardHeader>
            <form onSubmit={handleCreate}>
              <CardContent className="space-y-4 pt-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-300">Project Name *</label>
                  <input
                    type="text"
                    required
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    placeholder="e.g. Buck Converter 12V-to-5V"
                    className="w-full h-9 px-3 rounded-lg border border-zinc-700 bg-zinc-900 text-xs text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-300">Description</label>
                  <textarea
                    rows={3}
                    value={newProjectDesc}
                    onChange={(e) => setNewProjectDesc(e.target.value)}
                    placeholder="Engineering requirements, target specs, application..."
                    className="w-full p-2.5 rounded-lg border border-zinc-700 bg-zinc-900 text-xs text-white focus:outline-none focus:border-blue-500 resize-none"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-300">Domain Type</label>
                  <select
                    value={newProjectType}
                    onChange={(e) => setNewProjectType(e.target.value)}
                    className="w-full h-9 px-2.5 rounded-lg border border-zinc-700 bg-zinc-900 text-xs text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="circuit">Circuit / Schematic</option>
                    <option value="power">Power Electronics</option>
                    <option value="embedded">Embedded MCU</option>
                    <option value="rf">RF / Wireless</option>
                    <option value="thermal">Thermal Management</option>
                    <option value="battery">Battery / BMS</option>
                    <option value="general">General Hardware</option>
                  </select>
                </div>
              </CardContent>
              <div className="flex items-center justify-end gap-2 p-4 border-t border-zinc-800 bg-zinc-900/40">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowCreateModal(false)}
                  className="text-xs border-zinc-700 hover:bg-zinc-800 text-zinc-300"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={createMutation.isPending || !newProjectName.trim()}
                  className="text-xs bg-blue-600 hover:bg-blue-500 text-white"
                >
                  {createMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
                  Create Project
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Projects Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center p-12">
          <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
        </div>
      ) : projects.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-zinc-800 rounded-xl">
          <FolderGit2 className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-white">No engineering projects yet</h3>
          <p className="text-xs text-zinc-500 max-w-sm mx-auto mt-1 mb-4">
            Create your first project to start designing circuits and verifying schematics.
          </p>
          <Button onClick={() => setShowCreateModal(true)} size="sm" className="bg-blue-600 hover:bg-blue-500 text-xs">
            <Plus className="w-3.5 h-3.5 mr-1" />
            Create Project
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((proj: any) => {
            const Icon = TYPE_ICONS[proj.project_type] || Cpu;
            return (
              <Card
                key={proj.id}
                className="border-zinc-800 bg-zinc-900/50 hover:bg-zinc-900 hover:border-zinc-700 transition-all flex flex-col justify-between"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <Badge variant="outline" className="text-[10px] font-mono uppercase border-zinc-700 text-zinc-300">
                      {proj.project_type}
                    </Badge>
                    <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2 py-0.5 rounded-full uppercase">
                      {proj.status}
                    </span>
                  </div>
                  <div className="flex items-start gap-3 mt-3">
                    <div className="p-2 rounded-lg bg-zinc-950 border border-zinc-800 text-blue-400 shrink-0">
                      <Icon className="w-4 h-4" />
                    </div>
                    <div>
                      <CardTitle className="text-sm font-semibold text-white leading-tight">
                        {proj.name}
                      </CardTitle>
                      <CardDescription className="text-xs text-zinc-400 mt-1 line-clamp-2">
                        {proj.description || "No description provided."}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="pt-2 border-t border-zinc-800/60">
                  <div className="flex items-center justify-between pt-2">
                    <span className="text-[11px] font-mono text-zinc-500">
                      {new Date(proj.created_at).toLocaleDateString()}
                    </span>
                    <Button asChild size="sm" variant="ghost" className="h-7 text-xs text-blue-400 hover:text-blue-300 p-0">
                      <Link href={`/projects/${proj.id}`} className="flex items-center gap-1">
                        <span>Workspace</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
