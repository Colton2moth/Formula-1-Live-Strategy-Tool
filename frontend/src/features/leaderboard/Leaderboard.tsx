import { Panel } from "../../components/Panel";
import type { ApiDriver, TimingMode } from "../../types/race";
import { formatGap, formatLapTime, tyreColors } from "../../utils/raceDisplay";

type LeaderboardProps = {
  drivers: ApiDriver[];
  selectedDriver: ApiDriver;
  timingMode: TimingMode;
  onTimingModeChange: (mode: TimingMode) => void;
  onSelectDriver: (driverNumber: number) => void;
};

export function Leaderboard({ drivers, selectedDriver, timingMode, onTimingModeChange, onSelectDriver }: LeaderboardProps) {
  return (
    <Panel label="Live driver table">
      <div className="flex items-center justify-between gap-3 border-b border-app-line px-4 py-3">
        <div className="text-sm font-semibold text-white">Leaderboard</div>
        <div className="flex rounded-sm border border-app-line p-0.5" aria-label="Timing display mode">
          <button onClick={() => onTimingModeChange("interval")} className={`px-3 py-1 text-xs font-semibold ${timingMode === "interval" ? "bg-app-red text-white" : "text-app-muted"}`}>Interval</button>
          <button onClick={() => onTimingModeChange("leaderGap")} className={`px-3 py-1 text-xs font-semibold ${timingMode === "leaderGap" ? "bg-app-red text-white" : "text-app-muted"}`}>Leader gap</button>
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
            {drivers.map((driver) => {
              const isSelected = driver.driver_number === selectedDriver.driver_number;
              const gap = timingMode === "interval" ? formatGap(driver.interval_ahead) : formatGap(driver.gap_to_leader);
              return (
                <tr key={driver.driver_number} className={`border-b border-app-line/70 ${isSelected ? "bg-app-red/10" : ""}`}>
                  <td className="px-4 py-2"><span className="text-sm font-black tabular-nums text-white">{driver.position}</span></td>
                  <td className="px-4 py-2"><button onClick={() => onSelectDriver(driver.driver_number)} className="text-left"><span className="text-sm font-black text-white">{driver.acronym}</span><span className="ml-2 text-xs font-medium text-app-muted">{driver.name}</span></button></td>
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
  );
}