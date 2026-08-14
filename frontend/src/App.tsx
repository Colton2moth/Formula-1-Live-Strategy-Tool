import { useEffect, useMemo, useState } from "react";
import { fetchDriverPrediction, fetchRaceState, fetchTrack, isApiRequestError } from "./api/raceState";
import { ErrorScreen } from "./components/ErrorScreen";
import type { ErrorVariant } from "./components/ErrorScreen";
import { LoadingScreen } from "./components/LoadingScreen";
import { Leaderboard } from "./features/leaderboard/Leaderboard";
import { RaceHeader } from "./features/race-header/RaceHeader";
import { StrategyPanel } from "./features/strategy-panel/StrategyPanel";
import { TrackMap } from "./features/track-map/TrackMap";
import { Footer } from "./components/Footer";
import type { ApiPrediction, RaceState, TrackState } from "./types/race";

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
  const [livePrediction, setLivePrediction] = useState<{ driverNumber: number; prediction: ApiPrediction } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const retryDelay = (attempt: number) => Math.min(1000 * 2 ** attempt, 8000);

    async function load() {
      for (let attempt = 0; active; attempt += 1) {
        try {
          const [raceStateResponse, trackResponse] = await Promise.all([
            fetchRaceState(),
            fetchTrack(),
          ]);
          if (!active) return;
          setRaceState(raceStateResponse);
          setTrack(trackResponse);
          return;
        } catch (requestError: unknown) {
          if (!active) return;
          if (isApiRequestError(requestError) && requestError.status === 503) {
            await new Promise((resolve) => setTimeout(resolve, retryDelay(attempt)));
            continue;
          }
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Unable to load race data.",
          );
          return;
        }
      }
    }

    load();
    return () => {
      active = false;
    };
  }, []);

  const selectedDriver = raceState?.drivers.find((driver) => driver.driver_number === selectedDriverNumber) ?? null;
  const snapshotPrediction =
    raceState?.predictions.find((prediction) => prediction.driver_number === selectedDriver?.driver_number) ?? null;

  useEffect(() => {
    if (selectedDriverNumber === null) {
      setLivePrediction(null);
      return;
    }

    let active = true;
    fetchDriverPrediction(selectedDriverNumber)
      .then((prediction) => {
        if (active) setLivePrediction({ driverNumber: selectedDriverNumber, prediction });
      })
      .catch(() => {
        // Fall back to the snapshot prediction on error.
      });

    return () => {
      active = false;
    };
  }, [selectedDriverNumber]);

  const selectedPrediction =
    livePrediction?.driverNumber === selectedDriverNumber
      ? livePrediction.prediction
      : snapshotPrediction;
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
            PitPit
          </div>
          <div className="dashboard-brand-subtitle">F1 Live Strategy Tool</div>
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
      <Footer />
    </main>
  );
}

export default App;
