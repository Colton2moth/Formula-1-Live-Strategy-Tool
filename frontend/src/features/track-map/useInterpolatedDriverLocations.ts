import { useCallback, useEffect, useRef } from "react";
import type { DriverLocation } from "../../hooks/useLiveState";

export type MarkerClock = {
  speed: number;
  paused: boolean;
};

export const LIVE_MARKER_CLOCK: MarkerClock = { speed: 1, paused: false };

type Sample = { t: number; x: number; y: number };

const PRESENTATION_DELAY_MS = 280;
const MAX_SAMPLES_PER_DRIVER = 3;
const SEEK_RESET_EPS_MS = 2000;
const MAX_FRAME_DT_MS = 100;

function interpolate(samples: Sample[], t: number): { x: number; y: number } | null {
  if (samples.length === 0) {
    return null;
  }
  const first = samples[0];
  const last = samples[samples.length - 1];
  if (samples.length === 1 || t <= first.t) {
    return { x: first.x, y: first.y };
  }
  if (t >= last.t) {
    return { x: last.x, y: last.y };
  }
  for (let i = 0; i < samples.length - 1; i += 1) {
    const a = samples[i];
    const b = samples[i + 1];
    if (t >= a.t && t <= b.t) {
      const span = b.t - a.t;
      const progress = span > 0 ? (t - a.t) / span : 0;
      return {
        x: a.x + (b.x - a.x) * progress,
        y: a.y + (b.y - a.y) * progress,
      };
    }
  }
  return { x: last.x, y: last.y };
}

export function useInterpolatedDriverLocations(
  locations: ReadonlyMap<number, DriverLocation>,
  clock: MarkerClock,
) {
  const locationsRef = useRef(locations);
  locationsRef.current = locations;

  const historiesRef = useRef<Map<number, Sample[]>>(new Map());
  const elementsRef = useRef<Map<number, SVGGElement>>(new Map());
  const lastTransformRef = useRef<Map<number, string>>(new Map());
  const clockRef = useRef<MarkerClock>(clock);
  const presentationRef = useRef(0);
  const lastWallRef = useRef(0);
  const newestRef = useRef(-Infinity);
  const oldestRef = useRef(Infinity);
  const seededRef = useRef(false);
  const rafRef = useRef(0);

  useEffect(() => {
    clockRef.current = clock;
  }, [clock]);

  useEffect(() => {
    const histories = historiesRef.current;
    let incomingMin = Infinity;
    let incomingMax = -Infinity;
    for (const location of locations.values()) {
      if (location.timestamp < incomingMin) incomingMin = location.timestamp;
      if (location.timestamp > incomingMax) incomingMax = location.timestamp;
    }
    if (incomingMax === -Infinity) {
      return;
    }

    const prevNewest = newestRef.current;
    const reset = !seededRef.current || incomingMax < prevNewest - SEEK_RESET_EPS_MS;

    if (reset) {
      histories.clear();
      for (const [number, location] of locations) {
        histories.set(number, [{ t: location.timestamp, x: location.map_x, y: location.map_y }]);
      }
      seededRef.current = true;
      newestRef.current = incomingMax;
      oldestRef.current = incomingMin;
      presentationRef.current = incomingMax - PRESENTATION_DELAY_MS;
      return;
    }

    if (incomingMax > prevNewest) {
      newestRef.current = incomingMax;
      presentationRef.current = incomingMax - PRESENTATION_DELAY_MS;
    }
    if (incomingMin < oldestRef.current) {
      oldestRef.current = incomingMin;
    }

    for (const [number, location] of locations) {
      const history = histories.get(number);
      const t = location.timestamp;
      if (!history || history.length === 0) {
        histories.set(number, [{ t, x: location.map_x, y: location.map_y }]);
        continue;
      }
      const last = history[history.length - 1];
      if (t > last.t) {
        history.push({ t, x: location.map_x, y: location.map_y });
        if (history.length > MAX_SAMPLES_PER_DRIVER) history.shift();
      } else if (t === last.t) {
        last.x = location.map_x;
        last.y = location.map_y;
      } else {
        histories.set(number, [{ t, x: location.map_x, y: location.map_y }]);
      }
    }
  }, [locations]);

  useEffect(() => {
    const frame = (now: number) => {
      rafRef.current = window.requestAnimationFrame(frame);

      const lastWall = lastWallRef.current;
      if (lastWall === 0) {
        lastWallRef.current = now;
        return;
      }
      const dt = Math.min(Math.max(now - lastWall, 0), MAX_FRAME_DT_MS);
      lastWallRef.current = now;

      const { speed, paused } = clockRef.current;
      if (!paused) {
        presentationRef.current += dt * speed;
      }

      if (!seededRef.current) {
        return;
      }
      const oldest = oldestRef.current;
      const newest = newestRef.current;
      if (oldest > newest) {
        return;
      }
      let t = presentationRef.current;
      if (t > newest) t = newest;
      if (t < oldest) t = oldest;

      const elements = elementsRef.current;
      const lastTransforms = lastTransformRef.current;
      for (const [number, element] of elements) {
        const samples = historiesRef.current.get(number);
        if (!samples || samples.length === 0) continue;
        const point = interpolate(samples, t);
        if (!point) continue;
        const transform = `translate(${point.x}px, ${point.y}px)`;
        if (lastTransforms.get(number) !== transform) {
          lastTransforms.set(number, transform);
          element.style.transform = transform;
        }
      }
    };

    rafRef.current = window.requestAnimationFrame(frame);
    return () => window.cancelAnimationFrame(rafRef.current);
  }, []);

  const markerRefFactories = useRef<Map<number, (element: SVGGElement | null) => void>>(new Map());

  const registerMarker = useCallback((driverNumber: number) => {
    let factory = markerRefFactories.current.get(driverNumber);
    if (!factory) {
      factory = (element: SVGGElement | null) => {
        if (element) {
          elementsRef.current.set(driverNumber, element);
          const location = locationsRef.current.get(driverNumber);
          if (location) {
            element.style.transform = `translate(${location.map_x}px, ${location.map_y}px)`;
          }
        } else {
          elementsRef.current.delete(driverNumber);
          lastTransformRef.current.delete(driverNumber);
        }
      };
      markerRefFactories.current.set(driverNumber, factory);
    }
    return factory;
  }, []);

  return { registerMarker };
}
