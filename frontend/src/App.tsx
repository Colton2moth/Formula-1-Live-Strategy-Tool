import { useEffect, useMemo, useState } from "react";
import { fetchRaceState, fetchTrack } from "./api/raceState";
import { Leaderboard } from "./features/leaderboard/Leaderboard";
import { RaceHeader } from "./features/race-header/RaceHeader";
import { StrategyPanel } from "./features/strategy-panel/StrategyPanel";
import { TrackMap } from "./features/track-map/TrackMap";
import type { RaceState, TrackState } from "./types/race";

function App() {
  const [raceState, setRaceState] = useState<RaceState | null>(null);
  const [track, setTrack] = useState<TrackState | null>(null);
  const [selectedDriverNumber, setSelectedDriverNumber] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([fetchRaceState(), fetchTrack()])
      .then(([raceStateResponse, trackResponse]) => {
        if (!active) return;
        setRaceState(raceStateResponse);
        setTrack(trackResponse);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        setError(requestError instanceof Error ? requestError.message : "Unable to load race data.");
      });
    return () => {
      active = false;
    };
  }, []);

  const selectedDriver = raceState?.drivers.find((driver) => driver.driver_number === selectedDriverNumber) ?? null;
  const selectedPrediction =
    raceState?.predictions.find((prediction) => prediction.driver_number === selectedDriver?.driver_number) ?? null;
  const sortedDrivers = useMemo(
    () => [...(raceState?.drivers ?? [])].sort((a, b) => a.position - b.position),
    [raceState],
  );
  const toggleSelectedDriver = (driverNumber: number) => {
    setSelectedDriverNumber((currentDriverNumber) => (currentDriverNumber === driverNumber ? null : driverNumber));
  };

  if (error) {
    return (
      <main className="dashboard-shell">
        <div className="dashboard-state-card dashboard-state-card--error">
          <div role="heading" aria-level={1} className="dashboard-state-title">
            Race data unavailable
          </div>
          <div className="dashboard-state-message">{error}</div>
          <div className="dashboard-state-help">Start FastAPI, then refresh the Vite app.</div>
        </div>
      </main>
    );
  }

  if (!raceState || !track) {
    return (
      <main className="dashboard-shell">
        <div className="dashboard-state-card">
          <div role="heading" aria-level={1} className="dashboard-state-title">
            Loading race snapshot
          </div>
          <div className="dashboard-state-message">Waiting for the mock REST API.</div>
        </div>
      </main>
    );
  }

  return (
    <main className="dashboard-shell">
      <div className="dashboard-container">
        <div className="dashboard-brand">
          <div role="heading" aria-level={1} className="dashboard-brand-title">
            F1 Live Strategy Tool
          </div>
        </div>
        <div className="dashboard-layout">
          <div className="dashboard-stack">
            <TrackMap
              track={track}
              drivers={sortedDrivers}
              selectedDriver={selectedDriver}
              onSelectDriver={toggleSelectedDriver}
            />
            <RaceHeader session={raceState.session} />
          </div>
          <div className="dashboard-stack">
            <StrategyPanel selectedDriver={selectedDriver} prediction={selectedPrediction} />
            <Leaderboard
              drivers={sortedDrivers}
              selectedDriver={selectedDriver}
              onSelectDriver={toggleSelectedDriver}
            />
          </div>
        </div>
      </div>
    </main>
  );
}

export default App;
