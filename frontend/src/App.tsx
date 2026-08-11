import { useEffect, useMemo, useState } from "react";
import { fetchRaceState, fetchTrack } from "./api/raceState";
import { ErrorScreen } from "./components/ErrorScreen";
import type { ErrorVariant } from "./components/ErrorScreen";
import { LoadingScreen } from "./components/LoadingScreen";
import { Leaderboard } from "./features/leaderboard/Leaderboard";
import { RaceHeader } from "./features/race-header/RaceHeader";
import { StrategyPanel } from "./features/strategy-panel/StrategyPanel";
import { TrackMap } from "./features/track-map/TrackMap";
import type { RaceState, TrackState } from "./types/race";

function classifyError(message: string): ErrorVariant {
  if (message.includes("Failed to fetch") || message.includes("NetworkError")) {
    return "unavailable";
  }
  if (message.startsWith("Request failed:")) {
    return "server-error";
  }
  if (message.includes("did not match the expected shape")) {
    return "invalid-data";
  }
  return "server-error";
}

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
    return <ErrorScreen variant={classifyError(error)} message={error} />;
  }

  if (!raceState || !track) {
    return <LoadingScreen variant="connecting" />;
  }

  return (
    <main className="dashboard-shell">
      <div className="dashboard-container">
        <div className="dashboard-brand">
          <div role="heading" aria-level={1} className="dashboard-brand-title">
            F1 Live Strategy Tool
          </div>
        </div>
        <RaceHeader session={raceState.session} />
        <div className="dashboard-layout">
          <div className="dashboard-stack">
            <TrackMap
              track={track}
              session={raceState.session}
              drivers={sortedDrivers}
              selectedDriver={selectedDriver}
              onSelectDriver={toggleSelectedDriver}
            />
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
