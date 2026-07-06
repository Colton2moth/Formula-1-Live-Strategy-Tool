import { StatusChip } from "../../components/StatusChip";
import type { ApiSession, TrackState } from "../../types/race";

type RaceHeaderProps = {
  session: ApiSession;
  track: TrackState;
};

export function RaceHeader({ session, track }: RaceHeaderProps) {
  const flagTone: "green" | "red" = session.race_control_status === "GREEN" ? "green" : "red";

  return (
    <header className="grid gap-3 border-l-4 border-app-red bg-app-panel px-4 py-4 md:grid-cols-[1fr_auto] md:items-center">
      <div className="grid gap-1">
        <div role="heading" aria-level={1} className="text-2xl font-black uppercase leading-none tracking-normal text-white md:text-3xl">
          {session.meeting_name}
        </div>
        <div className="text-sm font-medium text-app-muted">{track.circuit_name} - mock REST snapshot</div>
      </div>
      <div className="flex flex-wrap gap-2 md:justify-end">
        <StatusChip label={session.session_status} />
        <StatusChip label={`${session.race_control_status} flag`} tone={flagTone} />
        <StatusChip label={`${session.session_name} - lap ${session.current_lap}/${session.total_laps}`} />
        <StatusChip label={`${session.air_temperature} C air - ${session.rainfall ? "wet" : "dry"}`} />
      </div>
    </header>
  );
}