import { useEffect, useMemo, useState } from "react";
import { fetchRaceState, fetchTrack } from "./api/raceState";
import { Leaderboard } from "./features/leaderboard/Leaderboard";
import { RaceHeader } from "./features/race-header/RaceHeader";
import { StrategyPanel } from "./features/strategy-panel/StrategyPanel";
import { TrackMap } from "./features/track-map/TrackMap";
import type { RaceState, TimingMode, TrackState } from "./types/race";

function App() {
  const [raceState, setRaceState] = useState<RaceState | null>(null);
  const [track, setTrack] = useState<TrackState | null>(null);
  const [selectedDriverNumber, setSelectedDriverNumber] = useState<number | null>(null);
  const [timingMode, setTimingMode] = useState<TimingMode>("interval");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([fetchRaceState(), fetchTrack()])
      .then(([raceStateResponse, trackResponse]) => {
        if (!active) return;
        setRaceState(raceStateResponse);
        setTrack(trackResponse);
        setSelectedDriverNumber(raceStateResponse.drivers[0]?.driver_number ?? null);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        setError(requestError instanceof Error ? requestError.message : "Unable to load race data.");
      });
    return () => {
      active = false;
    };
  }, []);

  const selectedDriver = raceState?.drivers.find((driver) => driver.driver_number === selectedDriverNumber) ?? raceState?.drivers[0] ?? null;
  const selectedPrediction = raceState?.predictions.find((prediction) => prediction.driver_number === selectedDriver?.driver_number) ?? null;
  const sortedDrivers = useMemo(() => [...(raceState?.drivers ?? [])].sort((a, b) => a.position - b.position), [raceState]);

  if (error) {
    return (
      <main className="min-h-screen bg-app-bg px-4 py-4 font-sans text-app-text md:px-6">
        <div className="mx-auto grid max-w-[760px] gap-3 border border-app-red bg-app-panel p-5">
          <div role="heading" aria-level={1} className="text-xl font-black uppercase text-white">Race data unavailable</div>
          <div className="text-sm font-medium leading-6 text-app-muted">{error}</div>
          <div className="text-sm font-semibold text-app-text">Start FastAPI, then refresh the Vite app.</div>
        </div>
      </main>
    );
  }

  if (!raceState || !track || !selectedDriver) {
    return (
      <main className="min-h-screen bg-app-bg px-4 py-4 font-sans text-app-text md:px-6">
        <div className="mx-auto grid max-w-[760px] gap-3 border border-app-line bg-app-panel p-5">
          <div role="heading" aria-level={1} className="text-xl font-black uppercase text-white">Loading race snapshot</div>
          <div className="text-sm font-medium leading-6 text-app-muted">Waiting for the mock REST API.</div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-app-bg px-4 py-4 font-sans text-app-text md:px-6">
      <div className="mx-auto grid max-w-[1440px] gap-4">
        <RaceHeader session={raceState.session} track={track} />
        <div className="grid gap-4 xl:grid-cols-[1.55fr_0.95fr]">
          <div className="grid gap-4">
            <TrackMap track={track} drivers={sortedDrivers} selectedDriver={selectedDriver} onSelectDriver={setSelectedDriverNumber} />
            <Leaderboard drivers={sortedDrivers} selectedDriver={selectedDriver} timingMode={timingMode} onTimingModeChange={setTimingMode} onSelectDriver={setSelectedDriverNumber} />
          </div>
          <StrategyPanel selectedDriver={selectedDriver} prediction={selectedPrediction} />
        </div>
      </div>
    </main>
  );
}

export default App;