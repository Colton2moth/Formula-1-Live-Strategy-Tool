import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { LiveSocketStatus } from "../../api/liveSocket";
import type { ApiSession } from "../../types/race";
import { RaceHeader } from "../race-header/RaceHeader";

type FlagExample = { key: string; label: string; status: string };
type TrackExample = { key: string; label: string; rainfall: boolean };
type ConnectionExample = { key: LiveSocketStatus; label: string };
type StaleExample = { key: string; label: string; stale: boolean };

const flagExamples: FlagExample[] = [
  { key: "green", label: "Green", status: "GREEN" },
  { key: "clear", label: "Clear", status: "CLEAR" },
  { key: "yellow", label: "Yellow", status: "YELLOW" },
  { key: "double-yellow", label: "Double Yellow", status: "DOUBLE YELLOW" },
  { key: "red", label: "Red", status: "RED" },
  { key: "blue", label: "Blue", status: "BLUE" },
  { key: "chequered", label: "Chequered", status: "CHEQUERED" },
  { key: "black-white", label: "Black & White", status: "BLACK AND WHITE" },
  { key: "safety-car", label: "Safety Car", status: "SAFETY CAR DEPLOYED" },
  { key: "safety-car-lap", label: "SC In This Lap", status: "SAFETY CAR IN THIS LAP" },
  { key: "vsc", label: "Virtual Safety Car", status: "VIRTUAL SAFETY CAR DEPLOYED" },
  { key: "vsc-ending", label: "VSC Ending", status: "VIRTUAL SAFETY CAR ENDING" },
  { key: "started", label: "Session Started", status: "SESSION STARTED" },
  { key: "finished", label: "Session Finished", status: "SESSION FINISHED" },
  { key: "aborted", label: "Session Aborted", status: "SESSION ABORTED" },
  { key: "unknown", label: "Unknown status", status: "UNKNOWN FLAG" },
];

const trackExamples: TrackExample[] = [
  { key: "dry", label: "Dry track", rainfall: false },
  { key: "wet", label: "Wet track", rainfall: true },
];

const connectionExamples: ConnectionExample[] = [
  { key: "connecting", label: "Connecting" },
  { key: "open", label: "Live" },
  { key: "reconnecting", label: "Reconnecting" },
];

const staleExamples: StaleExample[] = [
  { key: "fresh", label: "Fresh data", stale: false },
  { key: "stale", label: "Stale data", stale: true },
];

const baseSession: ApiSession = {
  meeting_name: "Bahrain Grand Prix",
  session_name: "Race",
  session_status: "Running",
  current_lap: 42,
  total_laps: 57,
  track_temperature: 31.4,
  air_temperature: 24.8,
  rainfall: false,
  race_control_status: "GREEN",
};

function sessionWith(overrides: Partial<ApiSession>): ApiSession {
  return { ...baseSession, ...overrides };
}

export function LiveStateWorkbench() {
  return (
    <main className="dashboard-shell">
      <div className="state-workbench">
        <div className="state-workbench-header">
          <div>
            <div role="heading" aria-level={1} className="state-workbench-heading">
              Live State Workbench
            </div>
            <div className="state-workbench-intro">
              RaceHeader rendered across every flag, track, connection, and staleness state.
            </div>
          </div>
          <Link to="/test" className="state-workbench-back">
            Back to test index
          </Link>
        </div>

        <section className="state-workbench-section" aria-labelledby="live-flags">
          <div id="live-flags" role="heading" aria-level={2} className="state-workbench-section-title">
            Flag status
          </div>
          <div className="state-workbench-grid live-state-grid">
            {flagExamples.map((example) => (
              <LivePreview key={example.key} caption={example.label}>
                <RaceHeader
                  session={sessionWith({ race_control_status: example.status })}
                  connectionStatus="open"
                />
              </LivePreview>
            ))}
          </div>
        </section>

        <section className="state-workbench-section" aria-labelledby="live-track">
          <div id="live-track" role="heading" aria-level={2} className="state-workbench-section-title">
            Track status
          </div>
          <div className="state-workbench-grid live-state-grid">
            {trackExamples.map((example) => (
              <LivePreview key={example.key} caption={example.label}>
                <RaceHeader
                  session={sessionWith({ rainfall: example.rainfall })}
                  connectionStatus="open"
                />
              </LivePreview>
            ))}
          </div>
        </section>

        <section className="state-workbench-section" aria-labelledby="live-connection">
          <div id="live-connection" role="heading" aria-level={2} className="state-workbench-section-title">
            Live connection status
          </div>
          <div className="state-workbench-grid live-state-grid">
            {connectionExamples.map((example) => (
              <LivePreview key={example.key} caption={example.label}>
                <RaceHeader session={baseSession} connectionStatus={example.key} />
              </LivePreview>
            ))}
          </div>
        </section>

        <section className="state-workbench-section" aria-labelledby="live-stale">
          <div id="live-stale" role="heading" aria-level={2} className="state-workbench-section-title">
            Data staleness
          </div>
          <div className="state-workbench-grid live-state-grid">
            {staleExamples.map((example) => (
              <LivePreview key={example.key} caption={example.label}>
                <RaceHeader session={baseSession} connectionStatus="open" stale={example.stale} />
              </LivePreview>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

function LivePreview({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <div className="live-state-preview">
      <div className="live-state-caption">{caption}</div>
      {children}
    </div>
  );
}
