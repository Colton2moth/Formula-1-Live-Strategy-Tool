import { StatusChip } from "../../components/StatusChip";
import type { ApiSession, TrackState } from "../../types/race";

type RaceHeaderProps = {
  session: ApiSession;
  track: TrackState;
};

export function RaceHeader({ session, track }: RaceHeaderProps) {
  const flagTone: "green" | "red" = session.race_control_status === "GREEN" ? "green" : "red";

  return (
    <header className="race-header">
      <div className="race-header-copy">
        <div role="heading" aria-level={1} className="race-header-title">
          {session.meeting_name}
        </div>
        <div className="race-header-subtitle">{track.circuit_name} - mock REST snapshot</div>
      </div>
      <div className="race-header-statuses">
        <StatusChip label={session.session_status} />
        <StatusChip label={`${session.race_control_status} flag`} tone={flagTone} />
        <StatusChip label={`${session.session_name} - lap ${session.current_lap}/${session.total_laps}`} />
        <StatusChip label={`${session.air_temperature} C air - ${session.rainfall ? "wet" : "dry"}`} />
      </div>
    </header>
  );
}