import type { CSSProperties } from "react";
import { Panel } from "../../components/Panel";

import type { ApiDriver, ApiPrediction } from "../../types/race";
import { formatUpdatedAt, tyreColors } from "../../utils/raceDisplay";

type StrategyPanelProps = {
  selectedDriver: ApiDriver | null;
  prediction: ApiPrediction | null;
  stale?: boolean;
};

type BarDatum = { laps: number; pct: number };

const COMPOUND_ORDER = ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"] as const;

export function StrategyPanel({ selectedDriver, prediction, stale = false }: StrategyPanelProps) {
  const selectedTeamColor = selectedDriver ? `#${selectedDriver.team_colour}` : "var(--color-line)";
  const selectedDriverName = selectedDriver ? splitDriverName(selectedDriver.name) : null;
  const summaryStyle = { "--strategy-team-colour": selectedTeamColor } as CSSProperties;
  const compoundProbabilities = prediction?.compound_probabilities ?? null;
  const highestCompoundProbability = compoundProbabilities
    ? Math.max(...COMPOUND_ORDER.map((compound) => compoundProbabilities[compound] ?? 0))
    : null;

  const bars: BarDatum[] = [
    { laps: 3, pct: Math.round((prediction?.pit_within_3_laps ?? 0) * 100) },
    { laps: 5, pct: Math.round((prediction?.pit_within_5_laps ?? 0) * 100) },
    { laps: 7, pct: Math.round((prediction?.pit_within_7_laps ?? 0) * 100) },
  ];
  const highestPitProbability = Math.max(...bars.map((bar) => bar.pct));

  return (
    <Panel
      label="AI strategy panel"
      icon="psychology"
      headerContent={
        selectedDriver && prediction ? (
          <div className="strategy-freshness-row">
            <span className="strategy-freshness-label">Last Updated:</span>
            <span className="strategy-freshness-value">{formatUpdatedAt(prediction.updated_at)}</span>
            {stale ? <span className="strategy-freshness-stale">Stale</span> : null}
          </div>
        ) : null
      }
    >
      <div className="strategy-panel-body">
        <div className="strategy-category-grid">
          <div className="strategy-driver-summary" style={summaryStyle}>
            <span className="strategy-eyebrow">Selected Driver</span>
            <div className="stat-category-body">
              {selectedDriverName ? (
                <>
                  <span className="strategy-driver-name">
                    {selectedDriverName.firstName ? (
                      <span className="strategy-driver-first-name">{selectedDriverName.firstName}</span>
                    ) : null}
                    <span className="strategy-driver-last-name">{selectedDriverName.lastName.toUpperCase()}</span>
                  </span>
                  <span className="strategy-driver-team">{selectedDriver?.team_name}</span>
                  <span className="strategy-driver-position">P{selectedDriver?.position}</span>
                </>
              ) : (
                <>
                  <span className="strategy-driver-empty">None selected</span>
                  <span className="strategy-driver-team">Select a driver.</span>
                </>
              )}
            </div>
          </div>

          {selectedDriver && prediction ? (
            <>
              <div className="strategy-category">
                <div className="strategy-category-title">Pit probability within</div>
                <div className="stat-category-body">
                  <div
                    className="strategy-pit-bars"
                    role="img"
                    aria-label={`Model estimate: ${bars[0].pct}% within 3 laps, ${bars[1].pct}% within 5 laps, ${bars[2].pct}% within 7 laps`}
                  >
                    {bars.map((bar) => (
                      <div key={bar.laps} className="strategy-pit-bar-col">
                        <span
                          className={`strategy-pit-bar-value ${bar.pct === highestPitProbability ? "" : "strategy-pit-bar-value--muted"}`}
                        >
                          {bar.pct}%
                        </span>
                        <div className="strategy-pit-bar-track">
                          <div className="strategy-pit-bar-fill" style={{ height: `${bar.pct}%` }} />
                        </div>
                        <span className="strategy-pit-bar-label">{bar.laps} Laps</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="strategy-category strategy-category--tyres">
                <div className="strategy-category-title">Likely next tyre</div>
                <div className="strategy-compound-breakdown">
                  {compoundProbabilities ? (
                    COMPOUND_ORDER.map((compound) => {
                      const color = tyreColors[compound] ?? "var(--color-line)";
                      const textColor =
                        compound === "HARD" || compound === "MEDIUM" || compound === "INTERMEDIATE"
                          ? "#111318"
                          : "#ffffff";
                      const value = Math.round(compoundProbabilities[compound] * 100);
                      const isHighest = compoundProbabilities[compound] === highestCompoundProbability;
                      const logoStyle = {
                        "--strategy-tyre-logo-colour": color,
                        "--strategy-tyre-logo-text": textColor,
                      } as CSSProperties;
                      return (
                        <div
                          key={compound}
                          className="strategy-compound-bar"
                          role="img"
                          aria-label={`${compound} probability ${value}%`}
                        >
                          <span
                            className={`strategy-compound-value ${isHighest ? "" : "strategy-compound-value--muted"}`}
                          >
                            {value}%
                          </span>
                          <div className="strategy-compound-track" aria-hidden="true">
                            <div
                              className="strategy-compound-fill"
                              style={{ height: `${value}%`, backgroundColor: color }}
                            />
                          </div>
                          <span className="strategy-tyre-logo" style={logoStyle}>
                            {compound.charAt(0)}
                          </span>
                        </div>
                      );
                    })
                  ) : (
                    <span className="strategy-category-unavailable">Compound data unavailable</span>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="strategy-empty-state">
              <div className="strategy-empty-title">
                {selectedDriver ? "Prediction unavailable" : "No driver selected"}
              </div>
              <div className="stat-category-body">
                <div className="strategy-empty-copy">
                  {selectedDriver
                    ? "No model estimate exists for the selected driver in the current snapshot."
                    : "Select a driver from the map or leaderboard to view strategy estimates."}
                </div>
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
