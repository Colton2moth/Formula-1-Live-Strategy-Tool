import { useState } from "react";

type Driver = {
  id: string;
  position: number;
  code: string;
  name: string;
  team: string;
  country: string;
  lastLap: string;
  interval: string;
  leaderGap: string;
  tyre: "Medium" | "Hard" | "Soft";
  tyreColor: string;
  teamColor: string;
  mapX: number;
  mapY: number;
};

const demoDrivers: Driver[] = [
  { id: "lec", position: 1, code: "LEC", name: "Charles Leclerc", team: "Ferrari", country: "MC", lastLap: "1:33.912", interval: "Leader", leaderGap: "Leader", tyre: "Medium", tyreColor: "#ffd447", teamColor: "#e10600", mapX: 68, mapY: 23 },
  { id: "ver", position: 2, code: "VER", name: "Max Verstappen", team: "Red Bull", country: "NL", lastLap: "1:34.104", interval: "+0.842", leaderGap: "+0.842", tyre: "Hard", tyreColor: "#f5f5f5", teamColor: "#3671c6", mapX: 78, mapY: 43 },
  { id: "nor", position: 3, code: "NOR", name: "Lando Norris", team: "McLaren", country: "GB", lastLap: "1:34.281", interval: "+1.112", leaderGap: "+1.954", tyre: "Medium", tyreColor: "#ffd447", teamColor: "#ff8000", mapX: 47, mapY: 72 },
  { id: "ham", position: 4, code: "HAM", name: "Lewis Hamilton", team: "Mercedes", country: "GB", lastLap: "1:34.510", interval: "+2.430", leaderGap: "+4.384", tyre: "Soft", tyreColor: "#ff3b3b", teamColor: "#27f4d2", mapX: 28, mapY: 58 },
  { id: "alo", position: 5, code: "ALO", name: "Fernando Alonso", team: "Aston Martin", country: "ES", lastLap: "1:35.021", interval: "+1.008", leaderGap: "+5.392", tyre: "Hard", tyreColor: "#f5f5f5", teamColor: "#229971", mapX: 18, mapY: 31 },
];

const selectedDriver = demoDrivers[0];
const demoPitWindows = [
  { label: "3 laps", value: 28 },
  { label: "5 laps", value: 54 },
  { label: "10 laps", value: 71 },
];
const demoCompounds = [
  { label: "Hard", value: 62, color: "#f5f5f5" },
  { label: "Medium", value: 27, color: "#ffd447" },
  { label: "Soft", value: 11, color: "#ff3b3b" },
];

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

function ProbabilityBar({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="grid gap-1">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold text-app-text">{label}</span>
        <span className="text-xs font-semibold tabular-nums text-app-muted">{value}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-sm bg-app-panelAlt" aria-label={`${label} probability ${value}%`}>
        <div className="h-full rounded-sm bg-app-red" style={{ width: `${value}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function App() {
  const [timingMode, setTimingMode] = useState<"interval" | "leaderGap">("interval");

  return (
    <main className="min-h-screen bg-app-bg px-4 py-4 font-sans text-app-text md:px-6">
      <div className="mx-auto grid max-w-[1440px] gap-4">
        <header className="grid gap-3 border-l-4 border-app-red bg-app-panel px-4 py-4 md:grid-cols-[1fr_auto] md:items-center">
          <div className="grid gap-1">
            <div role="heading" aria-level={1} className="text-2xl font-black uppercase leading-none tracking-normal text-white md:text-3xl">
              Canadian Grand Prix
            </div>
            <div className="text-sm font-medium text-app-muted">Circuit Gilles Villeneuve · Race strategy dashboard skeleton</div>
          </div>
          <div className="flex flex-wrap gap-2 md:justify-end">
            <StatusChip label="No live race data connected yet" />
            <StatusChip label="Green flag" tone="green" />
            <StatusChip label="Race · Lap 31/70" />
            <StatusChip label="21 C · Dry" />
          </div>
        </header>

        <div className="grid gap-4 xl:grid-cols-[1.55fr_0.95fr]">
          <div className="grid gap-4">
            <Panel label="Track map">
              <div className="relative min-h-[390px] overflow-hidden bg-app-panelAlt p-4">
                <svg viewBox="0 0 100 80" className="h-full min-h-[340px] w-full" role="img" aria-label="Static demo circuit map with selected driver markers">
                  <path d="M17 27 C20 8 49 8 67 17 C86 27 89 49 75 62 C60 78 33 74 21 61 C9 48 9 37 17 27 Z" fill="none" stroke="var(--color-track)" strokeWidth="5" strokeLinecap="round" />
                  <path d="M17 27 C20 8 49 8 67 17 C86 27 89 49 75 62 C60 78 33 74 21 61 C9 48 9 37 17 27 Z" fill="none" stroke="var(--color-f1-red)" strokeWidth="1.4" strokeLinecap="round" strokeDasharray="7 9" />
                  {demoDrivers.map((driver) => (
                    <g key={driver.id} tabIndex={0} aria-label={`${driver.code} ${driver.position === selectedDriver.position ? "selected driver" : "driver"} marker`}>
                      <circle cx={driver.mapX} cy={driver.mapY} r={driver.id === selectedDriver.id ? 4.7 : 3.8} fill={driver.teamColor} stroke={driver.id === selectedDriver.id ? "white" : "var(--color-bg)"} strokeWidth="1.8" />
                      <text x={driver.mapX + 4.8} y={driver.mapY + 1.3} fill="white" fontSize="4" fontWeight="700">
                        {driver.code}
                      </text>
                    </g>
                  ))}
                </svg>
                <div className="absolute left-4 top-4 rounded-sm border border-app-line bg-app-bg px-3 py-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-app-muted">Selected </span>
                  <span className="text-xs font-black text-white">{selectedDriver.code}</span>
                </div>
              </div>
            </Panel>

            <Panel label="Live driver table">
              <div className="flex items-center justify-between gap-3 border-b border-app-line px-4 py-3">
                <div className="text-sm font-semibold text-white">Leaderboard placeholder</div>
                <div className="flex rounded-sm border border-app-line p-0.5" aria-label="Timing display mode">
                  <button onClick={() => setTimingMode("interval")} className={`px-3 py-1 text-xs font-semibold ${timingMode === "interval" ? "bg-app-red text-white" : "text-app-muted"}`}>Interval</button>
                  <button onClick={() => setTimingMode("leaderGap")} className={`px-3 py-1 text-xs font-semibold ${timingMode === "leaderGap" ? "bg-app-red text-white" : "text-app-muted"}`}>Leader gap</button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] border-collapse">
                  <thead>
                    <tr className="border-b border-app-line text-left">
                      {["Pos", "Driver", "Team", "Last lap", "Gap", "Tyre", "Country"].map((label) => (
                        <th key={label} className="px-4 py-2"><span className="text-[11px] font-semibold uppercase tracking-wide text-app-muted">{label}</span></th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {demoDrivers.map((driver) => (
                      <tr key={driver.id} className={`border-b border-app-line/70 ${driver.id === selectedDriver.id ? "bg-app-red/10" : ""}`}>
                        <td className="px-4 py-2"><span className="text-sm font-black tabular-nums text-white">{driver.position}</span></td>
                        <td className="px-4 py-2"><span className="text-sm font-black text-white">{driver.code}</span><span className="ml-2 text-xs font-medium text-app-muted">{driver.name}</span></td>
                        <td className="px-4 py-2"><span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: driver.teamColor }} /><span className="ml-2 text-sm font-semibold text-app-text">{driver.team}</span></td>
                        <td className="px-4 py-2"><span className="text-sm font-semibold tabular-nums text-app-text">{driver.lastLap}</span></td>
                        <td className="px-4 py-2"><span className="text-sm font-semibold tabular-nums text-app-text">{driver[timingMode]}</span></td>
                        <td className="px-4 py-2"><span className="rounded-sm border border-app-line px-2 py-1 text-xs font-black uppercase text-white" style={{ borderColor: driver.tyreColor }}>{driver.tyre}</span></td>
                        <td className="px-4 py-2"><span className="text-sm font-semibold text-app-muted">{driver.country}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </div>

          <Panel label="AI strategy panel" prominent>
            <div className="grid gap-5 p-5">
              <div className="grid gap-1 border-l-4 border-app-red pl-4">
                <span className="text-xs font-semibold uppercase tracking-wide text-app-muted">Selected driver</span>
                <span className="text-4xl font-black uppercase leading-none text-white">{selectedDriver.code}</span>
                <span className="text-sm font-semibold text-app-muted">{selectedDriver.name} · {selectedDriver.team}</span>
              </div>

              <div className="grid grid-cols-3 gap-3">
                {demoPitWindows.map((window) => (
                  <div key={window.label} className="border border-app-line bg-app-panelAlt p-3">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-app-muted">{window.label}</div>
                    <div className="mt-2 text-2xl font-black tabular-nums text-white">{window.value}%</div>
                    <div className="mt-1 text-xs font-medium text-app-muted">pit probability</div>
                  </div>
                ))}
              </div>

              <div className="grid gap-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-black uppercase text-white">Likely next tyre</span>
                  <span className="rounded-sm bg-white px-2 py-1 text-xs font-black uppercase text-black">Hard</span>
                </div>
                {demoCompounds.map((compound) => (
                  <ProbabilityBar key={compound.label} label={compound.label} value={compound.value} color={compound.color} />
                ))}
              </div>

              <div className="grid gap-2 border-t border-app-line pt-4">
                <div className="text-sm font-semibold text-white">Model estimate placeholder</div>
                <div className="text-sm font-medium leading-6 text-app-muted">
                  Static layout data only. No live API, WebSocket, prediction model, or backend data is connected yet.
                </div>
                <div className="flex flex-wrap gap-2">
                  <StatusChip label="Snapshot unavailable" tone="red" />
                  <StatusChip label="Freshness pending" />
                  <StatusChip label="Demo UI state" />
                </div>
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </main>
  );
}

export default App;
