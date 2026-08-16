import { useMemo, useState } from "react";
import { useLiveState } from "../../hooks/useLiveState";
import type { ApiDriver, RaceState, TrackState } from "../../types/race";
import { Leaderboard } from "../leaderboard/Leaderboard";
import { RaceHeader } from "../race-header/RaceHeader";
import { StrategyPanel } from "../strategy-panel/StrategyPanel";
import { TrackMap } from "../track-map/TrackMap";

type RaceDashboardProps = {
  raceState: RaceState;
  track: TrackState;
};

export function RaceDashboard({ raceState, track }: RaceDashboardProps) {
  const [selectedDriverNumber, setSelectedDriverNumber] = useState<number | null>(null);

  const live = useLiveState(raceState);

  const selectedDriver = live.drivers.find((driver) => driver.driver_number === selectedDriverNumber) ?? null;
  const selectedPrediction = selectedDriver
    ? live.predictions.get(selectedDriver.driver_number) ?? null
    : null;
  const sortedDrivers = useMemo(
    () => [...live.drivers].sort((a, b) => a.position - b.position),
    [live.drivers],
  );
  const mapDrivers = useMemo<ApiDriver[]>(
    () =>
      sortedDrivers.map((driver) => {
        const location = live.locations.get(driver.driver_number);
        return location ? { ...driver, x: location.x, y: location.y } : driver;
      }),
    [sortedDrivers, live.locations],
  );
  const toggleSelectedDriver = (driverNumber: number) => {
    setSelectedDriverNumber((currentDriverNumber) => (currentDriverNumber === driverNumber ? null : driverNumber));
  };

  const session = live.session ?? raceState.session;

  return (
    <>
      <RaceHeader session={session} connectionStatus={live.status} />
      <div className="dashboard-layout">
        <div className="dashboard-stack">
          <TrackMap
            track={track}
            session={session}
            drivers={mapDrivers}
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
    </>
  );
}
