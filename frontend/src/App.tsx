import { useState } from "react";
import { ActivityToastStack } from "./components/ActivityToastStack";
import { BrandBar } from "./components/BrandBar";
import { ErrorScreen } from "./components/ErrorScreen";
import { Footer } from "./components/Footer";
import { LoadingScreen } from "./components/LoadingScreen";
import { RaceDashboard } from "./features/dashboard/RaceDashboard";
import { classifyError, useRaceData } from "./features/dashboard/useRaceData";
import { liveSource } from "./hooks/useLiveState";

function App() {
  const [reloadKey, setReloadKey] = useState(0);
  const { raceState, track, trackStatus, raceStateStatus, raceStateError } = useRaceData(
    reloadKey,
    liveSource,
  );

  const fatal = raceState === null && raceStateStatus === "error";

  return (
    <main className="dashboard-shell">
      <BrandBar />
      <ActivityToastStack />
      {fatal ? (
        <ErrorScreen
          variant={classifyError(raceStateError)}
          error={raceStateError ?? undefined}
          embedded
          onRetry={() => setReloadKey((key) => key + 1)}
        />
      ) : !raceState ? (
        <LoadingScreen variant="connecting" embedded />
      ) : (
        <div className="dashboard-container">
          <RaceDashboard
            raceState={raceState}
            track={track}
            trackStatus={trackStatus}
            source={liveSource}
            checkingLiveRace={raceStateStatus === "loading"}
            onCheckLiveRace={() => setReloadKey((key) => key + 1)}
          />
        </div>
      )}
      <Footer />
    </main>
  );
}

export default App;
