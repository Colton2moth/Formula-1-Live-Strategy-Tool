import { useMemo, useState } from "react";
import { liveSource, useRaceStream } from "../../hooks/useLiveState";
import type { DashboardSource } from "../../hooks/useLiveState";
import type { ApiDriver, RaceState, TrackState } from "../../types/race";
import { Leaderboard } from "../leaderboard/Leaderboard";
import { RaceHeader } from "../race-header/RaceHeader";
import { StrategyPanel } from "../strategy-panel/StrategyPanel";
import { TrackMap } from "../track-map/TrackMap";
import type { MarkerAnimationMode } from "../track-map/useDriverMarkers";
import { NoLiveRaceModal } from "./NoLiveRaceModal";
import type { ResourceStatus } from "./useRaceData";

type RaceDashboardProps = {
  raceState: RaceState;
  track: TrackState | null;
  trackStatus: ResourceStatus;
  source: DashboardSource;
  animationMode?: MarkerAnimationMode;
  checkingLiveRace?: boolean;
  onCheckLiveRace?: () => void;
};

export function RaceDashboard({ raceState, track, trackStatus, source, animationMode = { type: "live" }, checkingLiveRace = false, onCheckLiveRace }: RaceDashboardProps) {
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
  const isActiveRace =
    session.session_name.trim().toLowerCase() === "race" &&
    session.session_status.trim().toLowerCase() === "active";
  const showNoLiveRaceModal = source.socketPath === liveSource.socketPath && !isActiveRace;

  return (
    <>
      <div className="dashboard-layout">
        <div className="dashboard-stack dashboard-stack--leaderboard">
          <StrategyPanel
            selectedDriver={selectedDriver}
            prediction={selectedPrediction}
            stale={stream.stale}
          />
          <Leaderboard
            drivers={sortedDrivers}
            selectedDriver={selectedDriver}
            onSelectDriver={toggleSelectedDriver}
          />
        </div>
        <div className="dashboard-stack">
          <RaceHeader session={session} connectionStatus={stream.status} stale={stream.stale} />
          <TrackMap
            track={track}
            trackStatus={trackStatus}
            session={session}
            drivers={sortedDrivers}
            progress={stream.progress}
            resetGeneration={stream.resetGeneration}
            animationMode={animationMode}
            selectedDriver={selectedDriver}
            onSelectDriver={toggleSelectedDriver}
          />
        </div>
      </div>
      {showNoLiveRaceModal && onCheckLiveRace ? (
        <NoLiveRaceModal checking={checkingLiveRace} onCheckAgain={onCheckLiveRace} />
      ) : null}
    </>
  );
}
