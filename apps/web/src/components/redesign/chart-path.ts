export type ChartPathPoint = { x: number; y: number };

/**
 * Shape-preserving monotone cubic interpolation for recorded chart points.
 * The tangents are limited to neighbouring slopes (Fritsch-Carlson), so the
 * curve cannot invent a peak or trough between two observations.
 */
export function monotonePath(points: readonly ChartPathPoint[]) {
  if (!points.length) return "";
  if (points.length === 1) return `M${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;

  const gaps = points.slice(0, -1).map((point, index) => points[index + 1].x - point.x);
  // A duplicate or out-of-order timestamp is invalid for interpolation. The
  // safe polyline fallback keeps the observation visible without NaNs.
  if (gaps.some(gap => !Number.isFinite(gap) || gap <= 0)) {
    return points.map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
  }

  const slopes = gaps.map((gap, index) => (points[index + 1].y - points[index].y) / gap);
  const tangents = new Array<number>(points.length).fill(0);
  if (points.length === 2) {
    tangents[0] = slopes[0];
    tangents[1] = slopes[0];
  } else {
    for (let index = 1; index < points.length - 1; index += 1) {
      const previous = slopes[index - 1];
      const next = slopes[index];
      if (previous * next <= 0) {
        tangents[index] = 0;
        continue;
      }
      const previousGap = gaps[index - 1];
      const nextGap = gaps[index];
      const weightPrevious = 2 * nextGap + previousGap;
      const weightNext = nextGap + 2 * previousGap;
      tangents[index] = (weightPrevious + weightNext) / (weightPrevious / previous + weightNext / next);
    }

    const firstGap = gaps[0];
    let firstTangent = ((2 * firstGap + gaps[1]) * slopes[0] - firstGap * slopes[1]) / (firstGap + gaps[1]);
    if (firstTangent * slopes[0] <= 0) firstTangent = 0;
    else if (Math.abs(firstTangent) > 3 * Math.abs(slopes[0])) firstTangent = 3 * slopes[0];
    tangents[0] = firstTangent;

    const last = gaps.length - 1;
    const lastGap = gaps[last];
    let lastTangent = ((2 * lastGap + gaps[last - 1]) * slopes[last] - lastGap * slopes[last - 1]) / (lastGap + gaps[last - 1]);
    if (lastTangent * slopes[last] <= 0) lastTangent = 0;
    else if (Math.abs(lastTangent) > 3 * Math.abs(slopes[last])) lastTangent = 3 * slopes[last];
    tangents[tangents.length - 1] = lastTangent;
  }

  return points.slice(0, -1).reduce((path, point, index) => {
    const next = points[index + 1];
    const handle = gaps[index] / 3;
    return `${path} C${(point.x + handle).toFixed(2)} ${(point.y + tangents[index] * handle).toFixed(2)} ${(next.x - handle).toFixed(2)} ${(next.y - tangents[index + 1] * handle).toFixed(2)} ${next.x.toFixed(2)} ${next.y.toFixed(2)}`;
  }, `M${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`);
}

