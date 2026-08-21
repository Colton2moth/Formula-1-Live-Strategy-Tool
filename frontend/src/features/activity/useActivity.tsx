import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type ActivityTone = "neutral" | "amber";

export type ActivityOperation = {
  id: string;
  message: string;
  tone: ActivityTone;
};

type ActivityApi = {
  set: (id: string, message: string, tone?: ActivityTone) => void;
  clear: (id: string) => void;
};

const ActivityApiContext = createContext<ActivityApi | null>(null);
const ActivityOperationsContext = createContext<ActivityOperation[]>([]);

export const ACTIVITY_IDS = {
  raceState: "race-state",
  track: "track",
  retryRaceState: "race-state-retry",
  socket: "socket",
  snapshotRefresh: "snapshot-refresh",
  replaySessions: "replay-sessions",
  replayDownload: "replay-download",
} as const;

export const ACTIVITY_MESSAGES = {
  raceState: "Loading: getting race data",
  track: "Loading: getting track data",
  retryRaceState: "Retrying: race server is not ready",
  socketConnecting: "Connecting: opening live race connection",
  socketReconnecting: "Reconnecting: restoring live race connection",
  snapshotRefresh: "Loading: refreshing race data after reconnect",
  replaySessions: "Loading: getting replay library",
  replayDownload: "Downloading: preparing replay data",
} as const;

export function ActivityProvider({ children }: { children: ReactNode }) {
  const [operations, setOperations] = useState<ActivityOperation[]>([]);

  const set = useCallback((id: string, message: string, tone: ActivityTone = "neutral") => {
    setOperations((prev) => {
      const index = prev.findIndex((operation) => operation.id === id);
      const operation: ActivityOperation = { id, message, tone };
      if (index === -1) {
        return [...prev, operation];
      }
      const next = prev.slice();
      next[index] = operation;
      return next;
    });
  }, []);

  const clear = useCallback((id: string) => {
    setOperations((prev) => {
      if (!prev.some((operation) => operation.id === id)) {
        return prev;
      }
      return prev.filter((operation) => operation.id !== id);
    });
  }, []);

  const api = useMemo(() => ({ set, clear }), [set, clear]);

  return (
    <ActivityApiContext.Provider value={api}>
      <ActivityOperationsContext.Provider value={operations}>
        {children}
      </ActivityOperationsContext.Provider>
    </ActivityApiContext.Provider>
  );
}

export function useActivity(): ActivityApi {
  const context = useContext(ActivityApiContext);
  if (!context) {
    throw new Error("useActivity must be used within an ActivityProvider");
  }
  return context;
}

export function useActivityOperations(): ActivityOperation[] {
  return useContext(ActivityOperationsContext);
}
