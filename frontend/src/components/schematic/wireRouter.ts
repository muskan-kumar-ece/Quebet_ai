/**
 * Orthogonal wire routing and junction computation for schematic canvas.
 * Implements deterministic Manhattan routing for electrical net presentation.
 */

export interface Point {
  x: number;
  y: number;
}

/**
 * Calculates a clean orthogonal Manhattan SVG path from start to end.
 */
export function getOrthogonalPath(start: Point, end: Point): string {
  // If points are aligned horizontally or vertically, draw direct straight line
  if (start.x === end.x || start.y === end.y) {
    return `M ${start.x} ${start.y} L ${end.x} ${end.y}`;
  }

  // Manhattan midpoint route
  const midX = Math.round((start.x + end.x) / 2);
  return `M ${start.x} ${start.y} L ${midX} ${start.y} L ${midX} ${end.y} L ${end.x} ${end.y}`;
}

/**
 * Identifies solder junction dots (coordinates where 3 or more connections meet at the same point).
 */
export function computeJunctionDots(points: Point[]): Point[] {
  const coordCount = new Map<string, { count: number; pt: Point }>();

  for (const pt of points) {
    const key = `${Math.round(pt.x)},${Math.round(pt.y)}`;
    const existing = coordCount.get(key);
    if (existing) {
      existing.count += 1;
    } else {
      coordCount.set(key, { count: 1, pt });
    }
  }

  const junctions: Point[] = [];
  coordCount.forEach((val) => {
    if (val.count >= 3) {
      junctions.push(val.pt);
    }
  });

  return junctions;
}
