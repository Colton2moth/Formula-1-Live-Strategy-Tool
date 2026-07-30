import type { CSSProperties } from "react";
import { Panel } from "../../components/Panel";
import type { ApiDriver } from "../../types/race";
import { formatGap, formatLapTime, tyreColors } from "../../utils/raceDisplay";

const tyreCompoundLetters: Record<string, string> = {
  SOFT: "S",
  MEDIUM: "M",
  HARD: "H",
  INTERMEDIATE: "I",
  WET: "W",
};

const leaderboardColumnLabels = ["Pos", "Driver", "Team", "Last lap", "Gap / Interval", "Tyre", "Stops"] as const;

const leaderboardColumnSlug: Record<string, string> = {
  Pos: "pos",
  Driver: "driver",
  Team: "team",
  "Last lap": "last-lap",
  "Gap / Interval": "gap-interval",
  Tyre: "tyre",
  Stops: "stops",
};

type LeaderboardProps = {
  drivers: ApiDriver[];
  selectedDriver: ApiDriver | null;
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

export function Leaderboard({ drivers, selectedDriver, onSelectDriver }: LeaderboardProps) {
  return (
    <Panel label="Leaderboard">
      <div className="leaderboard-scroll">
        <table className="leaderboard-table">
          <thead>
            <tr className="leaderboard-header-row">
              {leaderboardColumnLabels.map((label) => (
                <th key={label} className={`leaderboard-header-cell leaderboard-col--${leaderboardColumnSlug[label]} ${label === "Gap / Interval" ? "leaderboard-timing-header" : ""}`}><span className="leaderboard-header-text">{label}</span></th>
              ))}
            </tr>
          </thead>
          <tbody>
            {drivers.map((driver) => {
              const isSelected = driver.driver_number === selectedDriver?.driver_number;
              const isLeader = driver.position === 1;
              const gapToLeader = isLeader ? "—" : formatGap(driver.gap_to_leader);
              const interval = isLeader ? "LEADER" : formatGap(driver.interval_ahead);
              const { firstName, lastName } = splitDriverName(driver.name);
              const compound = driver.compound.trim().toUpperCase();
              const tyreLetter = (tyreCompoundLetters[compound] ?? compound.charAt(0)) || "?";
              const tyreColor = tyreColors[compound] ?? "var(--color-line)";
              const tyreTextColor = compound === "HARD" || compound === "MEDIUM" ? "#111318" : "#ffffff";
              const tyreAgeLabel = Number.isFinite(driver.tyre_age) ? String(driver.tyre_age) : "--";
              const tyreAgeDescription = tyreAgeLabel === "--" ? "tyre age unavailable" : `${tyreAgeLabel} laps old`;
              const rowStyle = { "--team-accent-color": `#${driver.team_colour}` } as CSSProperties;
              const tyreStyle = { "--tyre-color": tyreColor, "--tyre-text-color": tyreTextColor } as CSSProperties;

              return (
                <tr
                  key={driver.driver_number}
                  className={`leaderboard-row ${isSelected ? "leaderboard-row--selected" : ""}`}
                  tabIndex={0}
                  aria-label={`${isSelected ? "Unselect" : "Select"} ${driver.acronym}`}
                  onClick={() => onSelectDriver(driver.driver_number)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") onSelectDriver(driver.driver_number);
                  }}
                  style={rowStyle}
                >
                  <td className="leaderboard-cell leaderboard-col--pos"><span className="leaderboard-position">{driver.position}</span></td>
                  <td className="leaderboard-cell leaderboard-col--driver"><span className="leaderboard-driver-name">{firstName ? <span className="leaderboard-driver-first-name">{firstName}</span> : null}<span className="leaderboard-driver-last-name">{lastName.toUpperCase()}</span></span></td>
                  <td className="leaderboard-cell leaderboard-col--team"><span className="leaderboard-team-dot" /><span className="leaderboard-team-name">{driver.team_name}</span></td>
                  <td className="leaderboard-cell leaderboard-col--last-lap"><span className="leaderboard-value">{formatLapTime(driver.last_lap_time)}</span></td>
                  <td className="leaderboard-cell leaderboard-col--gap-interval leaderboard-timing-cell">
                    <span className="leaderboard-timing">
                      <span className="leaderboard-timing-gap">{gapToLeader}</span>
                      <span className="leaderboard-timing-interval">{interval}</span>
                    </span>
                  </td>
                  <td className="leaderboard-cell leaderboard-col--tyre">
                    <span className="leaderboard-tyre-chip" aria-label={`${compound} tyre, ${tyreAgeDescription}`}>
                      <span className="leaderboard-tyre-dot" style={tyreStyle}>{tyreLetter}</span>
                      <span className={`leaderboard-tyre-age ${tyreAgeLabel === "--" ? "leaderboard-tyre-age--missing" : ""}`}>{tyreAgeLabel}</span>
                    </span>
                  </td>
                  <td className="leaderboard-cell leaderboard-col--stops"><span className="leaderboard-muted-value">{driver.pit_stops}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
