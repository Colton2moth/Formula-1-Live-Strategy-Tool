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
      <div className="grid gap-5 p-5">
        <div className="grid gap-1 border-l-4 border-app-red pl-4" style={{ borderColor: selectedTeamColor }}>
          <span className="text-xs font-semibold uppercase tracking-wide text-app-muted">Selected driver</span>
          <span className="text-4xl font-black uppercase leading-none text-white">{selectedDriver.acronym}</span>
          <span className="text-sm font-semibold text-app-muted">{selectedDriver.name} - {selectedDriver.team_name}</span>
        </div>

        {prediction ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div className="border border-app-line bg-app-panelAlt p-3">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-app-muted">Pit within 5 laps</div>
                <div className="mt-2 text-2xl font-black tabular-nums text-white">{pitProbability}%</div>
                <div className="mt-1 text-xs font-medium text-app-muted">model estimate</div>
              </div>
              <div className="border border-app-line bg-app-panelAlt p-3">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-app-muted">Predicted window</div>
                <div className="mt-2 text-2xl font-black tabular-nums text-white">{prediction.predicted_pit_window_start}-{prediction.predicted_pit_window_end}</div>
                <div className="mt-1 text-xs font-medium text-app-muted">race laps</div>
              </div>
            </div>
            <ProbabilityBar label="Pit probability" value={pitProbability ?? 0} />
            <div className="flex items-center justify-between gap-3 border-t border-app-line pt-4">
              <span className="text-sm font-black uppercase text-white">Likely next tyre</span>
              <span className="rounded-sm border px-2 py-1 text-xs font-black uppercase text-white" style={{ borderColor: tyreColors[prediction.predicted_next_compound] ?? "var(--color-line)" }}>{prediction.predicted_next_compound}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusChip label={`Updated ${formatUpdatedAt(prediction.updated_at)}`} />
              <StatusChip label="Mock model output" />
            </div>
          </>
        ) : (
          <div className="grid gap-2 border border-app-line bg-app-panelAlt p-4">
            <div className="text-sm font-semibold text-white">Prediction unavailable</div>
            <div className="text-sm font-medium leading-6 text-app-muted">No model estimate exists for the selected driver in the current snapshot.</div>
          </div>
        )}
      </div>
    </Panel>
  );
}