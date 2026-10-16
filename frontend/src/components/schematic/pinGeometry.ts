import type { SchematicComponent, SchematicObject, PinDescriptor } from "./types";

export interface SymbolPinLayout {
  pin_number: string;
  pin_name: string;
  dx: number;
  dy: number;
  type: string;
}

// Deterministic Pin Offsets for Standard Symbols
export function getStandardPinLayout(type: string, pins?: PinDescriptor[]): SymbolPinLayout[] {
  const normType = type.toLowerCase();

  switch (normType) {
    case "resistor":
      return [
        { pin_number: "1", pin_name: "1", dx: -35, dy: 0, type: "passive" },
        { pin_number: "2", pin_name: "2", dx: 35, dy: 0, type: "passive" },
      ];
    case "capacitor":
      return [
        { pin_number: "1", pin_name: "1", dx: -30, dy: 0, type: "passive" },
        { pin_number: "2", pin_name: "2", dx: 30, dy: 0, type: "passive" },
      ];
    case "inductor":
      return [
        { pin_number: "1", pin_name: "1", dx: -35, dy: 0, type: "passive" },
        { pin_number: "2", pin_name: "2", dx: 35, dy: 0, type: "passive" },
      ];
    case "diode":
    case "led":
      return [
        { pin_number: "1", pin_name: "A", dx: -30, dy: 0, type: "passive" },
        { pin_number: "2", pin_name: "K", dx: 30, dy: 0, type: "passive" },
      ];
    case "bjt":
    case "npn":
    case "pnp":
      return [
        { pin_number: "1", pin_name: "B", dx: -25, dy: 0, type: "input" },
        { pin_number: "2", pin_name: "C", dx: 25, dy: -25, type: "passive" },
        { pin_number: "3", pin_name: "E", dx: 25, dy: 25, type: "passive" },
      ];
    case "mosfet":
      return [
        { pin_number: "1", pin_name: "G", dx: -25, dy: 10, type: "input" },
        { pin_number: "2", pin_name: "D", dx: 25, dy: -25, type: "passive" },
        { pin_number: "3", pin_name: "S", dx: 25, dy: 25, type: "passive" },
      ];
    case "opamp":
      return [
        { pin_number: "1", pin_name: "IN-", dx: -35, dy: -15, type: "input" },
        { pin_number: "2", pin_name: "IN+", dx: -35, dy: 15, type: "input" },
        { pin_number: "3", pin_name: "OUT", dx: 35, dy: 0, type: "output" },
      ];
    case "vsource":
    case "battery":
      return [
        { pin_number: "1", pin_name: "+", dx: 0, dy: -30, type: "power_out" },
        { pin_number: "2", pin_name: "-", dx: 0, dy: 30, type: "power_out" },
      ];
    case "isource":
      return [
        { pin_number: "1", pin_name: "+", dx: 0, dy: -30, type: "power_out" },
        { pin_number: "2", pin_name: "-", dx: 0, dy: 30, type: "power_out" },
      ];
    case "ground":
      return [{ pin_number: "1", pin_name: "GND", dx: 0, dy: -20, type: "power_in" }];
    case "power":
      return [{ pin_number: "1", pin_name: "VCC", dx: 0, dy: 20, type: "power_out" }];
    case "connector":
      return [
        { pin_number: "1", pin_name: "1", dx: -20, dy: -10, type: "passive" },
        { pin_number: "2", pin_name: "2", dx: -20, dy: 10, type: "passive" },
      ];
    default: {
      if (pins && pins.length > 0) {
        const half = Math.ceil(pins.length / 2);
        return pins.map((p, idx) => {
          const isLeft = idx < half;
          const yOffset = -25 + (idx % half) * 25;
          return {
            pin_number: String(p.pin_number || idx + 1),
            pin_name: p.pin_name || `P${idx + 1}`,
            dx: isLeft ? -45 : 45,
            dy: yOffset,
            type: p.pin_type || "passive",
          };
        });
      }
      return [
        { pin_number: "1", pin_name: "1", dx: -35, dy: 0, type: "passive" },
        { pin_number: "2", pin_name: "2", dx: 35, dy: 0, type: "passive" },
      ];
    }
  }
}

// Calculate absolute pin coordinates given component location & rotation
export function getPinCoordinates(
  component: SchematicComponent,
  pinNumber: string,
  schemObj?: SchematicObject
): { x: number; y: number } {
  const posX = schemObj?.pos_x ?? 100;
  const posY = schemObj?.pos_y ?? 100;
  const rotation = schemObj?.rotation ?? 0;

  const layout = getStandardPinLayout(component.component_type, component.pins);
  const pin = layout.find((p) => p.pin_number === pinNumber) || layout[0] || { dx: 0, dy: 0 };

  const rad = (rotation * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);

  const rotDx = pin.dx * cos - pin.dy * sin;
  const rotDy = pin.dx * sin + pin.dy * cos;

  return {
    x: Math.round(posX + rotDx),
    y: Math.round(posY + rotDy),
  };
}
