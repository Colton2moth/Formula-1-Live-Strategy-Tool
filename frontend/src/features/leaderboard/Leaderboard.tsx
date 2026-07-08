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

function splitDriverName(name: string) {
  const nameParts = name.trim().split(/\s+/);
  const lastName = nameParts.pop() ?? name;

  return {
    firstName: nameParts.join(" "),
    lastName,
  };
}

export function Leaderboard({ drivers, selectedDriver, timingMode, onTimingModeChange, onSelectDriver }: LeaderboardProps) {
  return (
    <Panel label="Live driver table" className="leaderboard-panel">
      <div className="leaderboard-toolbar">
        <div className="leaderboard-title">Leaderboard</div>
        <div className="timing-toggle" aria-label="Timing display mode">
          <button onClick={() => onTimingModeChange("interval")} className={`timing-toggle-button ${timingMode === "interval" ? "timing-toggle-button--active" : ""}`}>Interval</button>
          <button onClick={() => onTimingModeChange("leaderGap")} className={`timing-toggle-button ${timingMode === "leaderGap" ? "timing-toggle-button--active" : ""}`}>Leader gap</button>
        </div>
      </div>
      <div className="leaderboard-scroll">
        <table className="leaderboard-table">
          <thead>
            <tr className="leaderboard-header-row">
              {["Pos", "Driver", "Team", "Last lap", "Gap", "Tyre", "Stops"].map((label) => (
                <th key={label} className="leaderboard-header-cell"><span className="leaderboard-header-text">{label}</span></th>
              ))}
            </tr>
          </thead>
          <tbody>
            {drivers.map((driver) => {
              const isSelected = driver.driver_number === selectedDriver.driver_number;
              const gap = timingMode === "interval" ? formatGap(driver.interval_ahead) : formatGap(driver.gap_to_leader);
              const { firstName, lastName } = splitDriverName(driver.name);
              return (
                <tr
                  key={driver.driver_number}
                  className={`leaderboard-row ${isSelected ? "leaderboard-row--selected" : ""}`}
                  tabIndex={0}
                  aria-label={`Select ${driver.acronym}`}
                  onClick={() => onSelectDriver(driver.driver_number)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") onSelectDriver(driver.driver_number);
                  }}
                  style={{ "--team-accent-color": `#${driver.team_colour}` } as React.CSSProperties}
                >
                  <td className="leaderboard-cell"><span className="leaderboard-position">{driver.position}</span></td>
                  <td className="leaderboard-cell"><span className="leaderboard-driver-name">{firstName ? <span className="leaderboard-driver-first-name">{firstName}</span> : null}<span className="leaderboard-driver-last-name">{lastName.toUpperCase()}</span></span></td>
                  <td className="leaderboard-cell"><span className="leaderboard-team-dot" style={{ backgroundColor: `#${driver.team_colour}` }} /><span className="leaderboard-team-name">{driver.team_name}</span></td>
                  <td className="leaderboard-cell"><span className="leaderboard-value">{formatLapTime(driver.last_lap_time)}</span></td>
                  <td className="leaderboard-cell"><span className="leaderboard-value">{gap}</span></td>
                  <td className="leaderboard-cell"><span className="leaderboard-tyre-chip" style={{ borderColor: tyreColors[driver.compound] ?? "var(--color-line)" }}>{driver.compound} {driver.tyre_age}L</span></td>
                  <td className="leaderboard-cell"><span className="leaderboard-muted-value">{driver.pit_stops}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
