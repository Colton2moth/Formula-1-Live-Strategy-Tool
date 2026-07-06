import { useEffect, useMemo, useState } from "react";

type ApiSession = {
  meeting_name: string;
  session_name: string;
  session_status: string;
  current_lap: number;
  total_laps: number;
  track_temperature: number;
  air_temperature: number;
  rainfall: boolean;
  race_control_status: string;
};

type ApiDriver = {
  driver_number: number;
  name: string;
  acronym: string;
  team_name: string;
  team_colour: string;
  position: number;
  compound: string;
  tyre_age: number;
  last_lap_time: number;
  gap_to_leader: number;
  interval_ahead: number | null;
  pit_stops: number;
};

type ApiPrediction = {
  driver_number: number;
  pit_within_5_laps: number;
  predicted_pit_window_start: number;
  predicted_pit_window_end: number;
  predicted_next_compound: string;
  updated_at: string;
};

type RaceState = {
  session: ApiSession;
  drivers: ApiDriver[];
  predictions: ApiPrediction[];
};

type TrackPoint = { x: number; y: number };
type TrackState = { circuit_name: string; path: TrackPoint[] };

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";
const tyreColors: Record<string, string> = {
  HARD: "#f5f5f5",
  MEDIUM: "#ffd447",
  SOFT: "#ff3b3b",
  INTERMEDIATE: "#43d65d",
  WET: "#3a7dff",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function assertRaceState(value: unknown): RaceState {
  if (!isRecord(value) || !isRecord(value.session) || !Array.isArray(value.drivers) || !Array.isArray(value.predictions)) {
    throw new Error("Race state response did not match the expected shape.");
  }
  return value as RaceState;
}

function assertTrackState(value: unknown): TrackState {
  if (!isRecord(value) || !Array.isArray(value.path)) {
    throw new Error("Track response did not match the expected shape.");
  }
  return value as TrackState;
}

async function fetchJson<T>(path: string, parse: (value: unknown) => T): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return parse(await response.json());
}

function formatLapTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remaining = (seconds - minutes * 60).toFixed(3).padStart(6, "0");
  return `${minutes}:${remaining}`;
}

function formatGap(value: number | null) {
  if (value === null || value === 0) {
    return "Leader";
  }
  return `+${value.toFixed(1)}`;
}

function formatUpdatedAt(value: string) {
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function trackPath(points: TrackPoint[]) {
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x * 100} ${point.y * 80}`).join(" ");
}

function markerPoint(points: TrackPoint[], index: number, total: number) {
  if (points.length === 0) {
    return { x: 50, y: 40 };
  }
  const pathIndex = Math.floor((index / Math.max(total, 1)) * (points.length - 1));
  const point = points[pathIndex] ?? points[0];
  return { x: point.x * 100, y: point.y * 80 };
}

function Panel({ label, children, prominent = false }: { label: string; children: React.ReactNode; prominent?: boolean }) {
  return (
    <section className={`rounded border bg-app-panel ${prominent ? "border-app-red" : "border-app-line"}`}>
      <div className={`border-b px-4 py-3 ${prominent ? "border-app-red" : "border-app-line"}`}>
        <div role="heading" aria-level={2} className="text-xs font-semibold uppercase tracking-wide text-app-muted">
          {label}
        </div>
      </div>
      {children}
    </section>
  );
}

function StatusChip({ label, tone = "neutral" }: { label: string; tone?: "red" | "green" | "neutral" }) {
  const toneClass = tone === "red" ? "border-app-red text-white" : tone === "green" ? "border-emerald-500 text-emerald-200" : "border-app-line text-app-muted";
  return <span className={`inline-flex items-center rounded-sm border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${toneClass}`}>{label}</span>;
}

function ProbabilityBar({ label, value, color = "var(--color-f1-red)" }: { label: string; value: number; color?: string }) {
  return (
    <div className="grid gap-1">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold text-app-text">{label}</span>
        <span className="text-xs font-semibold tabular-nums text-app-muted">{value}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-sm bg-app-panelAlt" aria-label={`${label} probability ${value}%`}>
        <div className="h-full rounded-sm" style={{ width: `${value}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function App() {
  const [raceState, setRaceState] = useState<RaceState | null>(null);
  const [track, setTrack] = useState<TrackState | null>(null);
  const [selectedDriverNumber, setSelectedDriverNumber] = useState<number | null>(null);
  const [timingMode, setTimingMode] = useState<"interval" | "leaderGap">("interval");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      fetchJson("/api/race-state", assertRaceState),
      fetchJson("/api/track", assertTrackState),
    ])
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
  const mapPath = track ? trackPath(track.path) : "";

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

  const flagTone = raceState.session.race_control_status === "GREEN" ? "green" : "red";
  const selectedTeamColor = `#${selectedDriver.team_colour}`;
  const pitProbability = selectedPrediction ? Math.round(selectedPrediction.pit_within_5_laps * 100) : null;

  return (
    <main className="min-h-screen bg-app-bg px-4 py-4 font-sans text-app-text md:px-6">
      <div className="mx-auto grid max-w-[1440px] gap-4">
        <header className="grid gap-3 border-l-4 border-app-red bg-app-panel px-4 py-4 md:grid-cols-[1fr_auto] md:items-center">
          <div className="grid gap-1">
            <div role="heading" aria-level={1} className="text-2xl font-black uppercase leading-none tracking-normal text-white md:text-3xl">
              {raceState.session.meeting_name}
            </div>
            <div className="text-sm font-medium text-app-muted">{track.circuit_name} - mock REST snapshot</div>
          </div>
          <div className="flex flex-wrap gap-2 md:justify-end">
            <StatusChip label={raceState.session.session_status} />
            <StatusChip label={`${raceState.session.race_control_status} flag`} tone={flagTone} />
            <StatusChip label={`${raceState.session.session_name} - lap ${raceState.session.current_lap}/${raceState.session.total_laps}`} />
            <StatusChip label={`${raceState.session.air_temperature} C air - ${raceState.session.rainfall ? "wet" : "dry"}`} />
          </div>
        </header>

        <div className="grid gap-4 xl:grid-cols-[1.55fr_0.95fr]">
          <div className="grid gap-4">
            <Panel label="Track map">
              <div className="relative min-h-[390px] overflow-hidden bg-app-panelAlt p-4">
                <svg viewBox="0 0 100 80" className="h-full min-h-[340px] w-full" role="img" aria-label={`${track.circuit_name} circuit map with selectable driver markers`}>
                  <path d={mapPath} fill="none" stroke="var(--color-track)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
                  <path d={mapPath} fill="none" stroke="var(--color-f1-red)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="7 9" />
                  {sortedDrivers.map((driver, index) => {
                    const marker = markerPoint(track.path, index, sortedDrivers.length);
                    const isSelected = driver.driver_number === selectedDriver.driver_number;
                    return (
                      <g key={driver.driver_number} role="button" tabIndex={0} className="cursor-pointer outline-none" aria-label={`Select ${driver.acronym} marker`} onClick={() => setSelectedDriverNumber(driver.driver_number)} onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") setSelectedDriverNumber(driver.driver_number);
                      }}>
                        <circle cx={marker.x} cy={marker.y} r={isSelected ? 4.7 : 3.8} fill={`#${driver.team_colour}`} stroke={isSelected ? "white" : "var(--color-bg)"} strokeWidth="1.8" />
                        <text x={marker.x + 4.8} y={marker.y + 1.3} fill="white" fontSize="4" fontWeight="700">{driver.acronym}</text>
                      </g>
                    );
                  })}
                </svg>
                <div className="absolute left-4 top-4 rounded-sm border border-app-line bg-app-bg px-3 py-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-app-muted">Selected </span>
                  <span className="text-xs font-black text-white">{selectedDriver.acronym}</span>
                </div>
              </div>
            </Panel>

            <Panel label="Live driver table">
              <div className="flex items-center justify-between gap-3 border-b border-app-line px-4 py-3">
                <div className="text-sm font-semibold text-white">Leaderboard</div>
                <div className="flex rounded-sm border border-app-line p-0.5" aria-label="Timing display mode">
                  <button onClick={() => setTimingMode("interval")} className={`px-3 py-1 text-xs font-semibold ${timingMode === "interval" ? "bg-app-red text-white" : "text-app-muted"}`}>Interval</button>
                  <button onClick={() => setTimingMode("leaderGap")} className={`px-3 py-1 text-xs font-semibold ${timingMode === "leaderGap" ? "bg-app-red text-white" : "text-app-muted"}`}>Leader gap</button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] border-collapse">
                  <thead>
                    <tr className="border-b border-app-line text-left">
                      {["Pos", "Driver", "Team", "Last lap", "Gap", "Tyre", "Stops"].map((label) => (
                        <th key={label} className="px-4 py-2"><span className="text-[11px] font-semibold uppercase tracking-wide text-app-muted">{label}</span></th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sortedDrivers.map((driver) => {
                      const isSelected = driver.driver_number === selectedDriver.driver_number;
                      const gap = timingMode === "interval" ? formatGap(driver.interval_ahead) : formatGap(driver.gap_to_leader);
                      return (
                        <tr key={driver.driver_number} className={`border-b border-app-line/70 ${isSelected ? "bg-app-red/10" : ""}`}>
                          <td className="px-4 py-2"><span className="text-sm font-black tabular-nums text-white">{driver.position}</span></td>
                          <td className="px-4 py-2"><button onClick={() => setSelectedDriverNumber(driver.driver_number)} className="text-left"><span className="text-sm font-black text-white">{driver.acronym}</span><span className="ml-2 text-xs font-medium text-app-muted">{driver.name}</span></button></td>
                          <td className="px-4 py-2"><span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: `#${driver.team_colour}` }} /><span className="ml-2 text-sm font-semibold text-app-text">{driver.team_name}</span></td>
                          <td className="px-4 py-2"><span className="text-sm font-semibold tabular-nums text-app-text">{formatLapTime(driver.last_lap_time)}</span></td>
                          <td className="px-4 py-2"><span className="text-sm font-semibold tabular-nums text-app-text">{gap}</span></td>
                          <td className="px-4 py-2"><span className="rounded-sm border border-app-line px-2 py-1 text-xs font-black uppercase text-white" style={{ borderColor: tyreColors[driver.compound] ?? "var(--color-line)" }}>{driver.compound} {driver.tyre_age}L</span></td>
                          <td className="px-4 py-2"><span className="text-sm font-semibold tabular-nums text-app-muted">{driver.pit_stops}</span></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>
          </div>

          <Panel label="AI strategy panel" prominent>
            <div className="grid gap-5 p-5">
              <div className="grid gap-1 border-l-4 border-app-red pl-4" style={{ borderColor: selectedTeamColor }}>
                <span className="text-xs font-semibold uppercase tracking-wide text-app-muted">Selected driver</span>
                <span className="text-4xl font-black uppercase leading-none text-white">{selectedDriver.acronym}</span>
                <span className="text-sm font-semibold text-app-muted">{selectedDriver.name} - {selectedDriver.team_name}</span>
              </div>

              {selectedPrediction ? (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="border border-app-line bg-app-panelAlt p-3">
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-app-muted">Pit within 5 laps</div>
                      <div className="mt-2 text-2xl font-black tabular-nums text-white">{pitProbability}%</div>
                      <div className="mt-1 text-xs font-medium text-app-muted">model estimate</div>
                    </div>
                    <div className="border border-app-line bg-app-panelAlt p-3">
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-app-muted">Predicted window</div>
                      <div className="mt-2 text-2xl font-black tabular-nums text-white">{selectedPrediction.predicted_pit_window_start}-{selectedPrediction.predicted_pit_window_end}</div>
                      <div className="mt-1 text-xs font-medium text-app-muted">race laps</div>
                    </div>
                  </div>
                  <ProbabilityBar label="Pit probability" value={pitProbability ?? 0} />
                  <div className="flex items-center justify-between gap-3 border-t border-app-line pt-4">
                    <span className="text-sm font-black uppercase text-white">Likely next tyre</span>
                    <span className="rounded-sm border px-2 py-1 text-xs font-black uppercase text-white" style={{ borderColor: tyreColors[selectedPrediction.predicted_next_compound] ?? "var(--color-line)" }}>{selectedPrediction.predicted_next_compound}</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <StatusChip label={`Updated ${formatUpdatedAt(selectedPrediction.updated_at)}`} />
                    <StatusChip label="Mock model output" />
                  </div>
                </>
              ) : (
                <div className="grid gap-2 border border-app-line bg-app-panelAlt p-4">
                  <div className="text-sm font-semibold text-white">Prediction unavailable</div>
                  <div className="text-sm font-medium leading-6 text-app-muted">No model estimate exists for the selected driver in the current snapshot.</div>
                </div>
              )}
            </div>
          </Panel>
        </div>
      </div>
    </main>
  );
}

export default App;
