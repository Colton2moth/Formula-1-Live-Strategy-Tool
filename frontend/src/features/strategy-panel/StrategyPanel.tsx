import type { CSSProperties } from "react";
import { Panel } from "../../components/Panel";
import { ProbabilityBar } from "../../components/ProbabilityBar";

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
  const summaryStyle = { "--strategy-team-colour": selectedTeamColor } as CSSProperties;
  const nextTyreColor = prediction ? tyreColors[prediction.predicted_next_compound] ?? "var(--color-line)" : "var(--color-line)";
  const nextTyreStyle = { "--strategy-tyre-colour": nextTyreColor } as CSSProperties;

  return (
    <Panel
      label="AI strategy panel"
      prominent
      headerContent={selectedDriver && prediction ? (
        <div className="strategy-freshness-row">
          <span className="strategy-freshness-label">Last Updated:</span>
          <span className="strategy-freshness-value">{formatUpdatedAt(prediction.updated_at)}</span>
        </div>
      ) : null}
    >
      <div className="strategy-panel-body">
        <div className="strategy-category-grid">
          <div className="strategy-driver-summary" style={summaryStyle}>
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
              <div className="strategy-category">
                <div className="strategy-category-title">Pit-window probabilities</div>
                <div className="strategy-pit-stats">
                  <div className="strategy-pit-stat">
                    <div className="strategy-card-label">Pit within 5 laps</div>
                    <div className="strategy-card-value">{pitProbability}%</div>
                    <div className="strategy-card-help">model estimate</div>
                  </div>
                  <div className="strategy-pit-stat">
                    <div className="strategy-card-label">Predicted window</div>
                    <div className="strategy-card-value">{prediction.predicted_pit_window_start}-{prediction.predicted_pit_window_end}</div>
                    <div className="strategy-card-help">race laps</div>
                  </div>
                </div>
                <ProbabilityBar label="Pit probability" value={pitProbability ?? 0} />
              </div>
              <div className="strategy-category">
                <div className="strategy-category-title">Likely next tyre</div>
                <span className="strategy-tyre-chip" style={nextTyreStyle}>{prediction.predicted_next_compound}</span>
              </div>
              <div className="strategy-category">
                <div className="strategy-category-title">Tyre-compound probabilities</div>
                <div className="strategy-category-unavailable">Breakdown unavailable</div>
                <div className="strategy-category-help">The current prediction provides only the most likely compound.</div>
              </div>
            </>
          ) : (
            <div className="strategy-empty-state">
              <div className="strategy-empty-title">{selectedDriver ? "Prediction unavailable" : "No driver selected"}</div>
              <div className="strategy-empty-copy">{selectedDriver ? "No model estimate exists for the selected driver in the current snapshot." : "Select a driver from the map or leaderboard to view strategy estimates."}</div>
            </div>
          )}
        </div>

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
