import { Panel } from "../../components/Panel";
import { ProbabilityBar } from "../../components/ProbabilityBar";
import { StatusChip } from "../../components/StatusChip";
import type { ApiDriver, ApiPrediction } from "../../types/race";
import { formatUpdatedAt, tyreColors } from "../../utils/raceDisplay";

type StrategyPanelProps = {
  selectedDriver: ApiDriver;
  prediction: ApiPrediction | null;
};

export function StrategyPanel({ selectedDriver, prediction }: StrategyPanelProps) {
  const selectedTeamColor = `#${selectedDriver.team_colour}`;
  const pitProbability = prediction ? Math.round(prediction.pit_within_5_laps * 100) : null;

  return (
    <Panel label="AI strategy panel" prominent>
      <div className="strategy-panel-body">
        <div className="strategy-driver-summary" style={{ borderColor: selectedTeamColor }}>
          <span className="strategy-eyebrow">Selected driver</span>
          <span className="strategy-driver-code">{selectedDriver.acronym}</span>
          <span className="strategy-driver-meta">{selectedDriver.name} - {selectedDriver.team_name}</span>
        </div>

        {prediction ? (
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
            <div className="strategy-empty-title">Prediction unavailable</div>
            <div className="strategy-empty-copy">No model estimate exists for the selected driver in the current snapshot.</div>
          </div>
        )}
      </div>
    </Panel>
  );
}