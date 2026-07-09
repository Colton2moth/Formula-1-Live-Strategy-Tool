import { Panel } from "../../components/Panel";
import { ProbabilityBar } from "../../components/ProbabilityBar";
import { StatusChip } from "../../components/StatusChip";
import type { ApiDriver, ApiPrediction } from "../../types/race";
import { formatUpdatedAt, tyreColors } from "../../utils/raceDisplay";

type StrategyPanelProps = {
  selectedDriver: ApiDriver | null;
  prediction: ApiPrediction | null;
};

export function StrategyPanel({ selectedDriver, prediction }: StrategyPanelProps) {
  const selectedTeamColor = selectedDriver ? `#${selectedDriver.team_colour}` : "var(--color-line)";
  const pitProbability = prediction ? Math.round(prediction.pit_within_5_laps * 100) : null;
  const selectedDriverName = selectedDriver ? splitDriverName(selectedDriver.name) : null;

  return (
    <Panel label="AI strategy panel" prominent>
      <div className="strategy-panel-body">
        <div className="strategy-driver-summary" style={{ borderColor: selectedTeamColor }}>
          <span className="strategy-eyebrow">Selected driver</span>
          {selectedDriverName ? (
            <>
              <span className="strategy-driver-name">
                {selectedDriverName.firstName ? <span className="strategy-driver-first-name">{selectedDriverName.firstName}</span> : null}
                <span className="strategy-driver-last-name">{selectedDriverName.lastName.toUpperCase()}</span>
              </span>
              <span className="strategy-driver-meta">{selectedDriver?.team_name}</span>
            </>
          ) : (
            <>
              <span className="strategy-driver-empty">None selected</span>
              <span className="strategy-driver-meta">Select a driver from the map or leaderboard.</span>
            </>
          )}
        </div>

        {selectedDriver && prediction ? (
          <>
            <div className="strategy-card-grid">
              <div className="strategy-card">
                <div className="strategy-card-label">Pit within 5 laps</div>
                <div className="strategy-card-value">{pitProbability}%</div>
                <div className="strategy-card-help">model estimate</div>
              </div>
              <div className="strategy-card">
                <div className="strategy-card-label">Predicted window</div>
                <div className="strategy-card-value">{prediction.predicted_pit_window_start}-{prediction.predicted_pit_window_end}</div>
                <div className="strategy-card-help">race laps</div>
              </div>
            </div>
            <ProbabilityBar label="Pit probability" value={pitProbability ?? 0} />
            <div className="strategy-next-tyre-row">
              <span className="strategy-next-tyre-label">Likely next tyre</span>
              <span className="strategy-tyre-chip" style={{ borderColor: tyreColors[prediction.predicted_next_compound] ?? "var(--color-line)" }}>{prediction.predicted_next_compound}</span>
            </div>
            <div className="strategy-status-row">
              <StatusChip label={`Updated ${formatUpdatedAt(prediction.updated_at)}`} />
              <StatusChip label="Mock model output" />
            </div>
          </>
        ) : (
          <div className="strategy-empty-state">
            <div className="strategy-empty-title">{selectedDriver ? "Prediction unavailable" : "No driver selected"}</div>
            <div className="strategy-empty-copy">{selectedDriver ? "No model estimate exists for the selected driver in the current snapshot." : "Select a driver from the map or leaderboard to view strategy estimates."}</div>
          </div>
        )}
      </div>
    </Panel>
  );
}

function splitDriverName(name: string) {
  const nameParts = name.trim().split(/\s+/);
  const lastName = nameParts.pop() ?? name;

  return {
    firstName: nameParts.join(" "),
    lastName,
  };
}
