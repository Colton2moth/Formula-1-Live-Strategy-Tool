import { useEffect, useState } from "react";
import { fetchTracks, toApiError } from "../../api/raceState";
import { ErrorScreen } from "../../components/ErrorScreen";
import { LoadingScreen } from "../../components/LoadingScreen";
import { classifyError } from "../dashboard/useRaceData";
import { TrackMap } from "../track-map/TrackMap";
import type { ApiSession, TrackState } from "../../types/race";

type PickerState =
  | { status: "loading" }
  | { status: "error"; error: unknown }
  | { status: "ready"; tracks: TrackState[] };

function sessionForTrack(track: TrackState): ApiSession {
  return {
    meeting_name: track.country_name ?? track.circuit_name,
    session_name: "Race",
    session_status: "active",
    current_lap: 0,
    total_laps: null,
    track_temperature: 0,
    air_temperature: 0,
    rainfall: false,
    race_control_status: "GREEN",
  };
}

function optionLabel(track: TrackState): string {
  const country = track.country_name?.trim() || "Unknown";
  return `${country} | ${track.circuit_name}`;
}

export function TrackMapPicker() {
  const [state, setState] = useState<PickerState>({ status: "loading" });
  const [selectedKey, setSelectedKey] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    fetchTracks()
      .then((tracks) => {
        if (!active) return;
        setState({ status: "ready", tracks });
        setSelectedKey((current) => current ?? tracks[0]?.circuit_key ?? null);
      })
      .catch((requestError: unknown) => {
        if (active) {
          setState({ status: "error", error: requestError });
        }
      });
    return () => {
      active = false;
    };
  }, []);

  if (state.status === "loading") {
    return <LoadingScreen variant="loading" />;
  }

  if (state.status === "error") {
    return <ErrorScreen variant={classifyError(state.error)} error={toApiError(state.error)} />;
  }

  const selectedTrack =
    state.tracks.find((track) => track.circuit_key === selectedKey) ?? state.tracks[0];

  if (!selectedTrack) {
    return (
      <main className="dashboard-shell">
        <div className="track-picker-empty">No track maps available.</div>
      </main>
    );
  }

  return (
    <main className="dashboard-shell">
      <div className="track-picker">
        <div role="heading" aria-level={1} className="track-picker-heading">
          Single Track Map
        </div>
        <label className="track-picker-control">
          <span className="track-picker-label">Circuit</span>
          <select
            className="track-picker-select"
            value={selectedTrack.circuit_key}
            onChange={(event) => setSelectedKey(Number(event.target.value))}
          >
            {state.tracks.map((track) => (
              <option key={track.circuit_key} value={track.circuit_key}>
                {optionLabel(track)}
              </option>
            ))}
          </select>
        </label>
        <TrackMap
          track={selectedTrack}
          trackStatus="ready"
          session={sessionForTrack(selectedTrack)}
          drivers={[]}
          progress={new Map()}
          selectedDriver={null}
          onSelectDriver={() => {}}
        />
      </div>
    </main>
  );
}
