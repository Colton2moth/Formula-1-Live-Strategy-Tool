import { useMemo, useState } from "react";
import { useRaceStream } from "../../hooks/useLiveState";
import type { DashboardSource } from "../../hooks/useLiveState";
import type { ApiDriver, RaceState, TrackState } from "../../types/race";
import { Leaderboard } from "../leaderboard/Leaderboard";
import { RaceHeader } from "../race-header/RaceHeader";
import { StrategyPanel } from "../strategy-panel/StrategyPanel";
import { TrackMap } from "../track-map/TrackMap";

type RaceDashboardProps = {
  raceState: RaceState;
  track: TrackState | null;
  source: DashboardSource;
};

export function RaceDashboard({ raceState, track, source }: RaceDashboardProps) {
  const [selectedDriverNumber, setSelectedDriverNumber] = useState<number | null>(null);

  const stream = useRaceStream(raceState, source);

  const selectedDriver = stream.drivers.find((driver) => driver.driver_number === selectedDriverNumber) ?? null;
  const selectedPrediction = selectedDriver
    ? stream.predictions.get(selectedDriver.driver_number) ?? null
    : null;
  const sortedDrivers = useMemo(
    () => [...stream.drivers].sort((a, b) => a.position - b.position),
    [stream.drivers],
  );
  const toggleSelectedDriver = (driverNumber: number) => {
    setSelectedDriverNumber((currentDriverNumber) => (currentDriverNumber === driverNumber ? null : driverNumber));
  };

  const session = stream.session ?? raceState.session;

  return (
    <>
      <div className="dashboard-layout">
        <div className="dashboard-stack">
          <StrategyPanel selectedDriver={selectedDriver} prediction={selectedPrediction} />
          <Leaderboard
            drivers={sortedDrivers}
            selectedDriver={selectedDriver}
            onSelectDriver={toggleSelectedDriver}
          />
        </div>
        <div className="dashboard-stack">
          <RaceHeader session={session} connectionStatus={stream.status} />
          <TrackMap
            track={track}
            session={session}
            drivers={sortedDrivers}
            locations={stream.locations}
            selectedDriver={selectedDriver}
            onSelectDriver={toggleSelectedDriver}
          />
        </div>
      </div>
    </>
  );
}
