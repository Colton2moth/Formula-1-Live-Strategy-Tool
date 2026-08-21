import { ActivityToastStack } from "./components/ActivityToastStack";
import { BrandBar } from "./components/BrandBar";
import { ErrorScreen } from "./components/ErrorScreen";
import { Footer } from "./components/Footer";
import { LoadingScreen } from "./components/LoadingScreen";
import { RaceDashboard } from "./features/dashboard/RaceDashboard";
import { classifyError, useRaceData } from "./features/dashboard/useRaceData";
import { liveSource } from "./hooks/useLiveState";

function App() {
  const { raceState, track, error } = useRaceData(0, liveSource);

  return (
    <main className="dashboard-shell">
      <BrandBar />
      <ActivityToastStack />
      {error ? (
        <ErrorScreen variant={classifyError(error)} error={error} embedded />
      ) : !raceState ? (
        <LoadingScreen variant="connecting" embedded />
      ) : (
        <div className="dashboard-container">
          <RaceDashboard raceState={raceState} track={track} source={liveSource} />
        </div>
      )}
      <Footer />
    </main>
  );
}

export default App;
