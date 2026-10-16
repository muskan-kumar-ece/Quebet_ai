import React from "react";
import { SchematicComponent, SchematicObject } from "./types";
import { getStandardPinLayout, getPinCoordinates } from "./pinGeometry";

export { getStandardPinLayout, getPinCoordinates };
export type { SymbolPinLayout } from "./pinGeometry";


// SVG Component Symbol Renderer
export const ComponentSymbol: React.FC<{
  component: SchematicComponent;
  schemObj: SchematicObject;
  isSelected: boolean;
  onPinClick?: (pinNumber: string, pinName?: string) => void;
  activeWireSourcePin?: { componentId: string; pinNumber: string } | null;
}> = ({ component, schemObj, isSelected, onPinClick, activeWireSourcePin }) => {
  const normType = component.component_type.toLowerCase();
  const pins = getStandardPinLayout(component.component_type, component.pins);

  const strokeColor = isSelected ? "#38bdf8" : "#94a3b8";
  const bodyColor = isSelected ? "rgba(56, 189, 248, 0.08)" : "rgba(30, 41, 59, 0.4)";

  const renderSymbolPath = () => {
    switch (normType) {
      case "resistor":
        return (
          <g>
            {/* Leads */}
            <line x1="-35" y1="0" x2="-20" y2="0" stroke={strokeColor} strokeWidth="2" />
            <line x1="20" y1="0" x2="35" y2="0" stroke={strokeColor} strokeWidth="2" />
            {/* Zig-Zag IEEE Resistor */}
            <path
              d="M -20 0 L -15 -8 L -7 8 L 0 -8 L 7 8 L 15 -8 L 20 0"
              fill="none"
              stroke={strokeColor}
              strokeWidth="2"
              strokeLinejoin="round"
            />
          </g>
        );
      case "capacitor":
        return (
          <g>
            <line x1="-30" y1="0" x2="-8" y2="0" stroke={strokeColor} strokeWidth="2" />
            <line x1="8" y1="0" x2="30" y2="0" stroke={strokeColor} strokeWidth="2" />
            <line x1="-8" y1="-16" x2="-8" y2="16" stroke={strokeColor} strokeWidth="2.5" />
            <line x1="8" y1="-16" x2="8" y2="16" stroke={strokeColor} strokeWidth="2.5" />
          </g>
        );
      case "inductor":
        return (
          <g>
            <line x1="-35" y1="0" x2="-24" y2="0" stroke={strokeColor} strokeWidth="2" />
            <line x1="24" y1="0" x2="35" y2="0" stroke={strokeColor} strokeWidth="2" />
            <path
              d="M -24 0 A 6 6 0 0 1 -12 0 A 6 6 0 0 1 0 0 A 6 6 0 0 1 12 0 A 6 6 0 0 1 24 0"
              fill="none"
              stroke={strokeColor}
              strokeWidth="2"
            />
          </g>
        );
      case "diode":
        return (
          <g>
            <line x1="-30" y1="0" x2="-14" y2="0" stroke={strokeColor} strokeWidth="2" />
            <line x1="14" y1="0" x2="30" y2="0" stroke={strokeColor} strokeWidth="2" />
            <polygon points="-14,-12 14,0 -14,12" fill={bodyColor} stroke={strokeColor} strokeWidth="2" />
            <line x1="14" y1="-12" x2="14" y2="12" stroke={strokeColor} strokeWidth="2" />
          </g>
        );
      case "led":
        return (
          <g>
            <line x1="-30" y1="0" x2="-14" y2="0" stroke={strokeColor} strokeWidth="2" />
            <line x1="14" y1="0" x2="30" y2="0" stroke={strokeColor} strokeWidth="2" />
            <polygon points="-14,-12 14,0 -14,12" fill={bodyColor} stroke={strokeColor} strokeWidth="2" />
            <line x1="14" y1="-12" x2="14" y2="12" stroke={strokeColor} strokeWidth="2" />
            {/* Emission Arrows */}
            <line x1="0" y1="-14" x2="8" y2="-22" stroke={strokeColor} strokeWidth="1.5" />
            <polyline points="4,-22 8,-22 8,-18" fill="none" stroke={strokeColor} strokeWidth="1.5" />
            <line x1="8" y1="-12" x2="16" y2="-20" stroke={strokeColor} strokeWidth="1.5" />
            <polyline points="12,-20 16,-20 16,-16" fill="none" stroke={strokeColor} strokeWidth="1.5" />
          </g>
        );
      case "bjt":
      case "npn":
        return (
          <g>
            <circle cx="0" cy="0" r="22" fill={bodyColor} stroke={strokeColor} strokeWidth="1.5" />
            <line x1="-25" y1="0" x2="-10" y2="0" stroke={strokeColor} strokeWidth="2" />
            <line x1="-10" y1="-14" x2="-10" y2="14" stroke={strokeColor} strokeWidth="3" />
            <line x1="-10" y1="-6" x2="18" y2="-20" stroke={strokeColor} strokeWidth="2" />
            <line x1="18" y1="-20" x2="25" y2="-25" stroke={strokeColor} strokeWidth="2" />
            <line x1="-10" y1="6" x2="18" y2="20" stroke={strokeColor} strokeWidth="2" />
            <line x1="18" y1="20" x2="25" y2="25" stroke={strokeColor} strokeWidth="2" />
            {/* Emitter Arrow */}
            <polygon points="12,17 18,20 16,13" fill={strokeColor} />
          </g>
        );
      case "mosfet":
        return (
          <g>
            <rect x="-18" y="-22" width="36" height="44" rx="4" fill={bodyColor} stroke={strokeColor} strokeWidth="1.5" />
            <line x1="-25" y1="10" x2="-18" y2="10" stroke={strokeColor} strokeWidth="2" />
            <line x1="18" y1="-15" x2="25" y2="-25" stroke={strokeColor} strokeWidth="2" />
            <line x1="18" y1="15" x2="25" y2="25" stroke={strokeColor} strokeWidth="2" />
            <text x="0" y="4" textAnchor="middle" fill={strokeColor} fontSize="9" fontFamily="monospace">
              FET
            </text>
          </g>
        );
      case "opamp":
        return (
          <g>
            <polygon points="-25,-25 25,0 -25,25" fill={bodyColor} stroke={strokeColor} strokeWidth="2" />
            <line x1="-35" y1="-15" x2="-25" y2="-15" stroke={strokeColor} strokeWidth="2" />
            <line x1="-35" y1="15" x2="-25" y2="15" stroke={strokeColor} strokeWidth="2" />
            <line x1="25" y1="0" x2="35" y2="0" stroke={strokeColor} strokeWidth="2" />
            <text x="-18" y="-12" fill={strokeColor} fontSize="12" fontWeight="bold">
              -
            </text>
            <text x="-18" y="19" fill={strokeColor} fontSize="12" fontWeight="bold">
              +
            </text>
          </g>
        );
      case "vsource":
      case "battery":
        return (
          <g>
            <circle cx="0" cy="0" r="20" fill={bodyColor} stroke={strokeColor} strokeWidth="2" />
            <line x1="0" y1="-30" x2="0" y2="-20" stroke={strokeColor} strokeWidth="2" />
            <line x1="0" y1="20" x2="0" y2="30" stroke={strokeColor} strokeWidth="2" />
            <text x="0" y="-6" textAnchor="middle" fill={strokeColor} fontSize="11" fontWeight="bold">
              +
            </text>
            <text x="0" y="14" textAnchor="middle" fill={strokeColor} fontSize="12" fontWeight="bold">
              -
            </text>
          </g>
        );
      case "ground":
        return (
          <g>
            <line x1="0" y1="-20" x2="0" y2="0" stroke={strokeColor} strokeWidth="2" />
            <line x1="-16" y1="0" x2="16" y2="0" stroke={strokeColor} strokeWidth="2.5" />
            <line x1="-10" y1="6" x2="10" y2="6" stroke={strokeColor} strokeWidth="2" />
            <line x1="-4" y1="12" x2="4" y2="12" stroke={strokeColor} strokeWidth="1.5" />
          </g>
        );
      case "power":
        return (
          <g>
            <line x1="0" y1="20" x2="0" y2="0" stroke={strokeColor} strokeWidth="2" />
            <polygon points="-10,0 0,-12 10,0" fill={strokeColor} />
          </g>
        );
      default: {
        // Generic IC / Regulator / MCU Box
        const boxHeight = Math.max(50, pins.length * 15);
        return (
          <g>
            <rect
              x="-35"
              y={-boxHeight / 2}
              width="70"
              height={boxHeight}
              rx="4"
              fill={bodyColor}
              stroke={strokeColor}
              strokeWidth="2"
            />
            {/* Notch at top */}
            <circle cx="0" cy={-boxHeight / 2} r="4" fill="#0f172a" stroke={strokeColor} strokeWidth="1.5" />
            {pins.map((p) => (
              <g key={p.pin_number}>
                <line x1={p.dx > 0 ? 35 : -35} y1={p.dy} x2={p.dx} y2={p.dy} stroke={strokeColor} strokeWidth="2" />
                <text
                  x={p.dx > 0 ? 30 : -30}
                  y={p.dy + 3}
                  textAnchor={p.dx > 0 ? "end" : "start"}
                  fill="#64748b"
                  fontSize="8"
                  fontFamily="monospace"
                >
                  {p.pin_name}
                </text>
              </g>
            ))}
          </g>
        );
      }
    }
  };

  return (
    <g transform={`translate(${schemObj.pos_x}, ${schemObj.pos_y}) rotate(${schemObj.rotation})`}>
      {/* Component Core Symbol */}
      {renderSymbolPath()}

      {/* Reference Designator and Value text (Un-rotated for legibility) */}
      <g transform={`rotate(${-schemObj.rotation})`}>
        <text
          x="0"
          y="-28"
          textAnchor="middle"
          fill={isSelected ? "#38bdf8" : "#f1f5f9"}
          fontSize="11"
          fontWeight="bold"
          fontFamily="system-ui"
        >
          {component.ref_des}
        </text>
        <text
          x="0"
          y="32"
          textAnchor="middle"
          fill="#94a3b8"
          fontSize="10"
          fontFamily="monospace"
        >
          {component.value}
        </text>
      </g>

      {/* Pin Connection Handles */}
      {pins.map((p) => {
        const isSourcePin =
          activeWireSourcePin &&
          activeWireSourcePin.componentId === component.id &&
          activeWireSourcePin.pinNumber === p.pin_number;

        return (
          <g
            key={p.pin_number}
            transform={`translate(${p.dx}, ${p.dy})`}
            className="cursor-crosshair group"
            onClick={(e) => {
              e.stopPropagation();
              onPinClick?.(p.pin_number, p.pin_name);
            }}
          >
            <circle
              r="7"
              fill={isSourcePin ? "#38bdf8" : "transparent"}
              className="hover:fill-sky-500/30 transition-colors"
            />
            <circle
              r="3.5"
              fill={isSourcePin ? "#38bdf8" : "#0f172a"}
              stroke={isSourcePin ? "#ffffff" : isSelected ? "#38bdf8" : "#64748b"}
              strokeWidth="2"
            />
          </g>
        );
      })}
    </g>
  );
};
