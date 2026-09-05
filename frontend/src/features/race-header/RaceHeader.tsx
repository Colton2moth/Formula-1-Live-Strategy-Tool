import type { ApiSession } from "../../types/race";
import type { LiveSocketStatus } from "../../api/liveSocket";
import { Panel } from "../../components/Panel";
import { StatusChip } from "../../components/StatusChip";
import { resolveSessionStatusChip } from "../dashboard/noLiveRace";

type RaceHeaderProps = {
  session: ApiSession;
  connectionStatus: LiveSocketStatus;
  stale?: boolean;
  isLiveSource?: boolean;
};

type FlagTone = "green" | "yellow" | "red" | "blue" | "neutral";

const raceControlStates: Record<string, { label: string; tone: FlagTone }> = {
  GREEN: { label: "Green", tone: "green" },
  CLEAR: { label: "Clear", tone: "green" },
  YELLOW: { label: "Yellow", tone: "yellow" },
  "DOUBLE YELLOW": { label: "Double Yellow", tone: "yellow" },
  RED: { label: "Red", tone: "red" },
  BLUE: { label: "Blue", tone: "blue" },
  CHEQUERED: { label: "Chequered", tone: "neutral" },
  "BLACK AND WHITE": { label: "Black & White", tone: "neutral" },
  "SAFETY CAR DEPLOYED": { label: "Safety Car", tone: "yellow" },
  "SAFETY CAR IN THIS LAP": { label: "SC In This Lap", tone: "yellow" },
  "VIRTUAL SAFETY CAR DEPLOYED": { label: "Virtual Safety Car", tone: "yellow" },
  "VIRTUAL SAFETY CAR ENDING": { label: "VSC Ending", tone: "yellow" },
  "SESSION STARTED": { label: "Started", tone: "green" },
  "SESSION FINISHED": { label: "Finished", tone: "neutral" },
  "SESSION ABORTED": { label: "Aborted", tone: "red" },
};

export function RaceHeader({ session, connectionStatus, stale = false, isLiveSource = true }: RaceHeaderProps) {
  const raceControl = getRaceControlState(session.race_control_status);
  const weatherIcon = session.rainfall ? "rainy" : "clear_day";
  const statusChip = resolveSessionStatusChip({ isLiveSource, connectionStatus, session });

  return (
    <Panel
      label="Race conditions"
      icon="sports_motorsports"
      headerContent={
        <div className="flex items-center gap-2">
          <StatusChip label={statusChip.label} tone={statusChip.tone} />
          {stale ? <StatusChip label="Stale" tone="amber" /> : null}
        </div>
      }
    >
      <div className="p-3">
      <div className="race-header-statuses">
        <div className="race-header-stat">
          <span className="race-header-stat-label">Flag</span>
          <span className="race-header-stat-reading">
            <span className={`material-symbols-rounded race-header-stat-icon race-header-stat-icon--${raceControl.tone}`} aria-hidden="true">
              flag
            </span>
            <span className={`race-header-stat-value race-header-stat-value--${raceControl.tone}`}>
              {raceControl.label}
            </span>
          </span>
        </div>
        <div className="race-header-stat">
          <span className="race-header-stat-label">Lap Number</span>
          <span className="race-header-stat-reading">
            <span className="material-symbols-rounded race-header-stat-icon" aria-hidden="true">
              laps
            </span>
            <span className="race-header-stat-value race-header-stat-value--numeric">
              {session.total_laps != null
                ? `${session.current_lap} / ${session.total_laps}`
                : session.current_lap}
            </span>
          </span>
        </div>
        <div className="race-header-stat">
          <span className="race-header-stat-label">Track status</span>
          <span className="race-header-stat-reading">
            <span className={`material-symbols-rounded race-header-stat-icon ${session.rainfall ? "race-header-stat-icon--rain" : "race-header-stat-icon--dry"}`} aria-hidden="true">
              {weatherIcon}
            </span>
            <span className="race-header-stat-value">{session.rainfall ? "Wet" : "Dry"}</span>
          </span>
        </div>
        <div className="race-header-stat">
          <span className="race-header-stat-label">Air Temp</span>
          <span className="race-header-stat-reading">
            <span className="material-symbols-rounded race-header-stat-icon" aria-hidden="true">
              device_thermostat
            </span>
            <span className="race-header-stat-value race-header-stat-value--numeric">
              {session.air_temperature.toFixed(1)}&deg;C
            </span>
          </span>
        </div>
        <div className="race-header-stat">
          <span className="race-header-stat-label">Track Temp</span>
          <span className="race-header-stat-reading">
            <span className="material-symbols-rounded race-header-stat-icon" aria-hidden="true">
              device_thermostat
            </span>
            <span className="race-header-stat-value race-header-stat-value--numeric">
              {session.track_temperature.toFixed(1)}&deg;C
            </span>
          </span>
        </div>
      </div>
      </div>
    </Panel>
  );
}
function getRaceControlState(status: string) {
  const normalizedStatus = status.trim().toUpperCase();
  return raceControlStates[normalizedStatus] ?? { label: normalizedStatus || "Unknown", tone: "neutral" as const };
}
