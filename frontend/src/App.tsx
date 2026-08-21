import { BrandBar } from "./components/BrandBar";
import { ErrorScreen } from "./components/ErrorScreen";
import { Footer } from "./components/Footer";
import { LoadingScreen } from "./components/LoadingScreen";
import { RaceDashboard } from "./features/dashboard/RaceDashboard";
import { classifyError, useRaceData } from "./features/dashboard/useRaceData";
import { liveSource } from "./hooks/useLiveState";

function App() {
  const { raceState, track, error } = useRaceData(0, liveSource);

  if (error) {
    return <ErrorScreen variant={classifyError(error)} message={error} />;
  }

  if (!raceState) {
    return <LoadingScreen variant="connecting" />;
  }

  return (
    <main className="dashboard-shell">
      <div className="dashboard-container">
        <BrandBar />
        <RaceDashboard raceState={raceState} track={track} source={liveSource} />
      </div>
      <Footer />
    </main>
  );
}

export default App;
