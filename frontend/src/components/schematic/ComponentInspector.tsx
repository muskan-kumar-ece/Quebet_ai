"use client";

import React, { useState, useEffect } from "react";
import { useCircuitWorkspace } from "./useCircuitWorkspace";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getStandardPinLayout } from "./symbols";
import {
  Check,
  AlertTriangle,
  ExternalLink,
  Edit2,
  Trash2,
  Cpu,
} from "lucide-react";

interface ComponentInspectorProps {
  onUpdateComponent?: (id: string, updates: any) => Promise<void>;
  onDeleteComponent?: (id: string) => Promise<void>;
}

export const ComponentInspector: React.FC<ComponentInspectorProps> = ({
  onUpdateComponent,
  onDeleteComponent,
}) => {
  const {
    components,
    nets,
    connections,
    selectedComponentId,
    updateComponentProperty,
    deleteComponent,
  } = useCircuitWorkspace();

  const component = components.find((c) => c.id === selectedComponentId);

  const [editValue, setEditValue] = useState("");
  const [editTolerance, setEditTolerance] = useState("");
  const [editPackage, setEditPackage] = useState("");
  const [editManufacturer, setEditManufacturer] = useState("");
  const [editPartNumber, setEditPartNumber] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (component) {
      setEditValue(component.value || "");
      setEditTolerance(component.tolerance || "");
      setEditPackage(component.package || "");
      setEditManufacturer(component.manufacturer || "");
      setEditPartNumber(component.part_number || "");
    }
  }, [component]);

  if (!component) {
    return (
      <Card className="bg-zinc-900/60 border-zinc-800 text-zinc-400 p-6 text-center text-sm">
        Select a component on the schematic canvas to inspect electrical parameters and pin connectivity.
      </Card>
    );
  }

  const standardPins = getStandardPinLayout(component.component_type, component.pins);
  const netMap = new Map(nets.map((n) => [n.id, n]));

  // Identify connected vs unconnected pins
  const componentConns = connections.filter((c) => c.component_id === component.id);
  const pinNetMap = new Map(componentConns.map((c) => [c.pin_number, c.net_id]));

  const handleSave = async () => {
    setIsSaving(true);
    const updates = {
      value: editValue,
      tolerance: editTolerance,
      package: editPackage,
      manufacturer: editManufacturer,
      part_number: editPartNumber,
    };
    updateComponentProperty(component.id, updates);
    if (onUpdateComponent) {
      await onUpdateComponent(component.id, updates);
    }
    setIsSaving(false);
  };

  const handleDelete = async () => {
    if (onDeleteComponent) {
      await onDeleteComponent(component.id);
    }
    deleteComponent(component.id);
  };

  return (
    <Card className="bg-zinc-900/80 border-zinc-800 shadow-xl overflow-hidden">
      <CardHeader className="p-4 border-b border-zinc-800/80 bg-zinc-900/90 flex flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-sky-950/80 border border-sky-800 flex items-center justify-center text-sky-400">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <CardTitle className="text-base font-semibold text-zinc-100 flex items-center gap-2">
              {component.ref_des}
              <Badge variant="outline" className="text-[10px] text-zinc-400 uppercase font-mono">
                {component.component_type}
              </Badge>
            </CardTitle>
            <span className="text-xs text-zinc-500 font-mono">ID: {component.id.slice(0, 8)}...</span>
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          className="h-7 w-7 p-0 text-red-400 border-red-900/60 hover:bg-red-950/40"
          onClick={handleDelete}
          title="Delete Component"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </CardHeader>

      <CardContent className="p-4 space-y-5 text-sm">
        {/* Editable Engineering Properties */}
        <div className="space-y-3">
          <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Parametric Properties
          </span>
          <div className="grid grid-cols-2 gap-2.5">
            <div>
              <label className="text-[11px] text-zinc-400 block mb-1">Value</label>
              <input
                type="text"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                className="w-full h-8 px-2.5 bg-zinc-950 border border-zinc-700/80 rounded text-xs text-zinc-200 font-mono focus:border-sky-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-[11px] text-zinc-400 block mb-1">Tolerance</label>
              <input
                type="text"
                value={editTolerance}
                placeholder="e.g. 1%"
                onChange={(e) => setEditTolerance(e.target.value)}
                className="w-full h-8 px-2.5 bg-zinc-950 border border-zinc-700/80 rounded text-xs text-zinc-200 font-mono focus:border-sky-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-[11px] text-zinc-400 block mb-1">Package</label>
              <input
                type="text"
                value={editPackage}
                placeholder="e.g. 0805, TO-220"
                onChange={(e) => setEditPackage(e.target.value)}
                className="w-full h-8 px-2.5 bg-zinc-950 border border-zinc-700/80 rounded text-xs text-zinc-200 font-mono focus:border-sky-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-[11px] text-zinc-400 block mb-1">Part Number</label>
              <input
                type="text"
                value={editPartNumber}
                placeholder="e.g. RC0805FR-0710KL"
                onChange={(e) => setEditPartNumber(e.target.value)}
                className="w-full h-8 px-2.5 bg-zinc-950 border border-zinc-700/80 rounded text-xs text-zinc-200 font-mono focus:border-sky-500 focus:outline-none"
              />
            </div>
          </div>

          <Button
            size="sm"
            onClick={handleSave}
            disabled={isSaving}
            className="w-full h-7 text-xs bg-sky-600 hover:bg-sky-500 text-white font-medium"
          >
            {isSaving ? "Saving..." : "Apply Parameter Changes"}
          </Button>
        </div>

        {/* Pinout & Electrical Connectivity (Section 14) */}
        <div className="space-y-2 pt-2 border-t border-zinc-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Pinout & Electrical Nets
            </span>
            <span className="text-[10px] text-zinc-500 font-mono">
              {componentConns.length}/{standardPins.length} Connected
            </span>
          </div>

          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {standardPins.map((pin) => {
              const netId = pinNetMap.get(pin.pin_number);
              const connectedNet = netId ? netMap.get(netId) : null;
              const isConnected = !!connectedNet;

              return (
                <div
                  key={pin.pin_number}
                  className="flex items-center justify-between p-2 rounded bg-zinc-950/60 border border-zinc-800/80 text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-5 text-center font-mono text-zinc-400 font-bold">
                      {pin.pin_number}
                    </span>
                    <span className="text-zinc-200 font-medium">{pin.pin_name}</span>
                    <Badge variant="outline" className="text-[9px] text-zinc-500 uppercase px-1 py-0">
                      {pin.type}
                    </Badge>
                  </div>

                  {isConnected ? (
                    <Badge className="bg-emerald-950/60 border-emerald-800 text-emerald-400 font-mono text-[10px] flex items-center gap-1">
                      <Check className="w-3 h-3" />
                      {connectedNet?.name}
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-amber-400/80 border-amber-900/60 bg-amber-950/20 font-mono text-[10px] flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      Unconnected
                    </Badge>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
