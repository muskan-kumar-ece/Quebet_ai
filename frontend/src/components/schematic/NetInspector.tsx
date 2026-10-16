"use client";

import React, { useState, useEffect } from "react";
import { useCircuitWorkspace } from "./useCircuitWorkspace";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Network, Trash2, CheckCircle2, Zap } from "lucide-react";

interface NetInspectorProps {
  onUpdateNet?: (id: string, updates: any) => Promise<void>;
  onDeleteNet?: (id: string) => Promise<void>;
}

export const NetInspector: React.FC<NetInspectorProps> = ({ onUpdateNet, onDeleteNet }) => {
  const {
    nets,
    components,
    connections,
    selectedNetId,
    deleteNet,
  } = useCircuitWorkspace();

  const net = nets.find((n) => n.id === selectedNetId);

  const [netName, setNetName] = useState("");
  const [netType, setNetType] = useState("signal");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (net) {
      setNetName(net.name);
      setNetType(net.net_type);
    }
  }, [net]);

  if (!net) {
    return null;
  }

  const compMap = new Map(components.map((c) => [c.id, c]));
  const netConnections = connections.filter((c) => c.net_id === net.id);

  const handleSave = async () => {
    setIsSaving(true);
    if (onUpdateNet) {
      await onUpdateNet(net.id, { name: netName, net_type: netType });
    }
    setIsSaving(false);
  };

  const handleDelete = async () => {
    if (onDeleteNet) {
      await onDeleteNet(net.id);
    }
    deleteNet(net.id);
  };

  return (
    <Card className="bg-zinc-900/80 border-zinc-800 shadow-xl overflow-hidden">
      <CardHeader className="p-4 border-b border-zinc-800/80 bg-zinc-900/90 flex flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-950/80 border border-emerald-800 flex items-center justify-center text-emerald-400">
            <Network className="w-4 h-4" />
          </div>
          <div>
            <CardTitle className="text-base font-semibold text-zinc-100 flex items-center gap-2">
              {net.name}
              <Badge variant="outline" className="text-[10px] text-zinc-400 uppercase font-mono">
                {net.net_type}
              </Badge>
            </CardTitle>
            <span className="text-xs text-zinc-500 font-mono">ID: {net.id.slice(0, 8)}...</span>
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          className="h-7 w-7 p-0 text-red-400 border-red-900/60 hover:bg-red-950/40"
          onClick={handleDelete}
          title="Delete Net"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </CardHeader>

      <CardContent className="p-4 space-y-4 text-sm">
        {/* Editable Net Properties */}
        <div className="space-y-3">
          <div>
            <label className="text-[11px] text-zinc-400 block mb-1">Net Identifier</label>
            <input
              type="text"
              value={netName}
              onChange={(e) => setNetName(e.target.value)}
              className="w-full h-8 px-2.5 bg-zinc-950 border border-zinc-700/80 rounded text-xs text-zinc-200 font-mono focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="text-[11px] text-zinc-400 block mb-1">Electrical Classification</label>
            <select
              value={netType}
              onChange={(e) => setNetType(e.target.value)}
              className="w-full h-8 px-2.5 bg-zinc-950 border border-zinc-700/80 rounded text-xs text-zinc-200 font-mono focus:border-emerald-500 focus:outline-none"
            >
              <option value="signal">Signal (Standard Conductor)</option>
              <option value="power">Power Rail (VCC / VDD / VIN)</option>
              <option value="ground">Ground Reference (GND / AGND)</option>
              <option value="clock">Clock Line (High Frequency)</option>
            </select>
          </div>

          <Button
            size="sm"
            onClick={handleSave}
            disabled={isSaving}
            className="w-full h-7 text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-medium"
          >
            {isSaving ? "Saving..." : "Update Net Attributes"}
          </Button>
        </div>

        {/* Bound Components and Pins */}
        <div className="space-y-2 pt-2 border-t border-zinc-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Connected Nodes ({netConnections.length})
            </span>
          </div>

          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {netConnections.map((conn) => {
              const comp = compMap.get(conn.component_id);
              return (
                <div
                  key={conn.id}
                  className="flex items-center justify-between p-2 rounded bg-zinc-950/60 border border-zinc-800/80 text-xs"
                >
                  <span className="font-mono text-zinc-300 font-semibold">
                    {comp?.ref_des || "Unknown"}.Pin {conn.pin_number}
                  </span>
                  <Badge variant="outline" className="text-[9px] text-zinc-400">
                    {comp?.value}
                  </Badge>
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
