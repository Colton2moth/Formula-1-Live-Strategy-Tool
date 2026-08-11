import type { CSSProperties } from "react";
import { Panel } from "../../components/Panel";

import type { ApiDriver, ApiPrediction } from "../../types/race";
import { formatUpdatedAt, tyreColors } from "../../utils/raceDisplay";

type StrategyPanelProps = {
  selectedDriver: ApiDriver | null;
  prediction: ApiPrediction | null;
};

type BarDatum = { laps: number; pct: number };

export function StrategyPanel({ selectedDriver, prediction }: StrategyPanelProps) {
  const selectedTeamColor = selectedDriver ? `#${selectedDriver.team_colour}` : "var(--color-line)";
  const selectedDriverName = selectedDriver ? splitDriverName(selectedDriver.name) : null;
  const summaryStyle = { "--strategy-team-colour": selectedTeamColor } as CSSProperties;
  const nextTyreCompound = prediction?.predicted_next_compound.trim().toUpperCase() ?? "";
  const nextTyreColor = tyreColors[nextTyreCompound] ?? "var(--color-line)";
  const nextTyreTextColor = nextTyreCompound === "HARD" || nextTyreCompound === "MEDIUM" ? "#111318" : "#ffffff";
  const nextTyreStyle = { "--strategy-tyre-colour": nextTyreColor, "--strategy-tyre-text-colour": nextTyreTextColor } as CSSProperties;

  const bars: BarDatum[] = [
    { laps: 3, pct: Math.round((prediction?.pit_within_3_laps ?? 0) * 100) },
    { laps: 5, pct: Math.round((prediction?.pit_within_5_laps ?? 0) * 100) },
    { laps: 7, pct: Math.round((prediction?.pit_within_7_laps ?? 0) * 100) },
  ];

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
                <div className="strategy-category-title">Pit probability within</div>
                <div className="stat-category-body">
                  <div className="strategy-pit-bars" role="img" aria-label={`Model estimate: ${bars[0].pct}% within 3 laps, ${bars[1].pct}% within 5 laps, ${bars[2].pct}% within 7 laps`}>
                    {bars.map((bar) => (
                      <div key={bar.laps} className="strategy-pit-bar-col">
                        <span className="strategy-pit-bar-label">{bar.laps} Laps</span>
                        <div className="strategy-pit-bar-track">
                          <div
                            className="strategy-pit-bar-fill"
                            style={{ height: `${bar.pct}%` }}
                          />
                        </div>
                        <span className="strategy-pit-bar-value">{bar.pct}%</span>
                      </div>
                    ))}
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
