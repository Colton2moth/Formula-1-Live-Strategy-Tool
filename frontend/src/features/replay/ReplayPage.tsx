import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { stopReplay } from "../../api/replay";
import { BrandBar } from "../../components/BrandBar";
import { Footer } from "../../components/Footer";
import { Panel } from "../../components/Panel";
import { RaceDashboard } from "../dashboard/RaceDashboard";
import { useRaceData } from "../dashboard/useRaceData";
import { replaySourceFor } from "../../hooks/useLiveState";
import { ReplayControls } from "./ReplayControls";
import { ReplayProgress } from "./ReplayProgress";
import { grandPrixName, useReplay } from "./useReplay";

export function ReplayPage() {
  const [reloadKey, setReloadKey] = useState(0);
  const onSeeded = useCallback(() => setReloadKey((key) => key + 1), []);
  const replay = useReplay(onSeeded);

  const source = useMemo(
    () => (replay.replayId ? replaySourceFor(replay.replayId) : null),
    [replay.replayId],
  );
  const { raceState, track, error } = useRaceData(reloadKey, source);

  const replayIdRef = useRef<string | null>(null);
  useEffect(() => {
    replayIdRef.current = replay.replayId;
  }, [replay.replayId]);

  useEffect(() => {
    return () => {
      if (replayIdRef.current) {
        void stopReplay(replayIdRef.current);
      }
    };
  }, []);

  const banner = replay.selectedSession
    ? `REPLAY — ${replay.selectedSession.year} ${grandPrixName(replay.selectedSession)}`
    : "REPLAY";

  const canSeek =
    (replay.status === "running" ||
      replay.status === "paused" ||
      replay.status === "finished") &&
    !replay.busy;

  return (
    <main className="dashboard-shell">
      <div className="dashboard-container">
        <BrandBar replayMode />
        <div className="replay-banner" role="status">
          {banner}
        </div>
        <ReplayControls {...replay} />
        <ReplayProgress
          progress={replay.progress}
          onSeek={replay.seek}
          onSeekLap={replay.seekLap}
          canSeek={canSeek}
        />
        {error ? (
          <Panel label="Race data">
            <div className="p-4">
              <div className="text-base font-black uppercase tracking-wide text-white">
                Unable to load race data
              </div>
              <div className="mt-1 text-sm font-medium leading-6 text-app-muted">{error.message}</div>
            </div>
          </Panel>
        ) : !raceState || !source ? (
          <Panel label="Race data">
            <div className="p-4">
              <div className="text-base font-black uppercase tracking-wide text-white">
                Loading race data
              </div>
              <div className="mt-1 text-sm font-medium leading-6 text-app-muted">
                Fetching session, drivers, and track data.
              </div>
            </div>
          </Panel>
        ) : (
          <RaceDashboard raceState={raceState} track={track} source={source} />
        )}
      </div>
      <Footer />
    </main>
  );
}
