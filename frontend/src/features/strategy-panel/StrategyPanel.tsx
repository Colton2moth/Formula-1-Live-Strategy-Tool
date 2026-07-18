import type { CSSProperties } from "react";
import { Panel } from "../../components/Panel";

import type { ApiDriver, ApiPrediction } from "../../types/race";
import { formatUpdatedAt, tyreColors } from "../../utils/raceDisplay";

type StrategyPanelProps = {
  selectedDriver: ApiDriver | null;
  prediction: ApiPrediction | null;
};

export function StrategyPanel({ selectedDriver, prediction }: StrategyPanelProps) {
  const selectedTeamColor = selectedDriver ? `#${selectedDriver.team_colour}` : "var(--color-line)";
  const pitProbability = Math.round((prediction?.pit_within_5_laps ?? 0) * 100);
  const selectedDriverName = selectedDriver ? splitDriverName(selectedDriver.name) : null;
  const summaryStyle = { "--strategy-team-colour": selectedTeamColor } as CSSProperties;
  const nextTyreCompound = prediction?.predicted_next_compound.trim().toUpperCase() ?? "";
  const nextTyreColor = tyreColors[nextTyreCompound] ?? "var(--color-line)";
  const nextTyreTextColor = nextTyreCompound === "HARD" || nextTyreCompound === "MEDIUM" ? "#111318" : "#ffffff";
  const nextTyreStyle = { "--strategy-tyre-colour": nextTyreColor, "--strategy-tyre-text-colour": nextTyreTextColor } as CSSProperties;

  return (
    <Panel
      label="AI strategy panel"
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
            <span className="strategy-eyebrow">Selected Driver</span>
            <div className="stat-category-body">
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
                  <span className="strategy-driver-meta">Select a driver.</span>
                </>
              )}
            </div>
          </div>

          {selectedDriver && prediction ? (
            <>
              <div className="strategy-category">
                <div className="strategy-category-title">Pit within 5 laps</div>
                <div className="stat-category-body">
                  <div className="strategy-pit-probability" aria-label={`${pitProbability}% model estimate for pitting within 5 laps`}>
                    <svg className="strategy-pit-ring" viewBox="0 0 100 100" aria-hidden="true">
                      <circle className="strategy-pit-ring-track" cx="50" cy="50" r="50" pathLength="100" />
                      <circle
                        className="strategy-pit-ring-progress"
                        cx="50"
                        cy="50"
                        r="50"
                        pathLength="100"
                        style={{ "--strategy-pit-progress": 100 - pitProbability } as CSSProperties}
                      />
                    </svg>
                    <div className="strategy-pit-stat">
                      <div className="strategy-card-value">{pitProbability}%</div>
                      <div className="strategy-card-help">Model Estimate</div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="strategy-category">
                <div className="strategy-category-title">Predicted window</div>
                <div className="stat-category-body">
                  <div className="strategy-pit-stat">
                    <div className="strategy-card-value">{prediction.predicted_pit_window_start}-{prediction.predicted_pit_window_end}</div>
                    <div className="strategy-card-help">race laps</div>
                  </div>
                </div>
              </div>
              <div className="strategy-category">
                <div className="strategy-category-title">Likely next tyre</div>
                <div className="stat-category-body">
                  <span className="strategy-tyre-chip" style={nextTyreStyle} aria-label={`${nextTyreCompound} tyre`}>
                    {nextTyreCompound.charAt(0) || "?"}
                  </span>
                </div>
              </div>
            </>
          ) : (
            <div className="strategy-empty-state">
              <div className="strategy-empty-title">{selectedDriver ? "Prediction unavailable" : "No driver selected"}</div>
              <div className="stat-category-body">
                <div className="strategy-empty-copy">{selectedDriver ? "No model estimate exists for the selected driver in the current snapshot." : "Select a driver from the map or leaderboard to view strategy estimates."}</div>
              </div>
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
