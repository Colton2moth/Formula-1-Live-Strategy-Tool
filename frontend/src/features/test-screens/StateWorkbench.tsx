import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ActivityToastStack } from "../../components/ActivityToastStack";
import { ErrorScreen } from "../../components/ErrorScreen";
import { LoadingScreen } from "../../components/LoadingScreen";
import { classifyError } from "../dashboard/useRaceData";
import { ACTIVITY_IDS, ACTIVITY_MESSAGES, useActivity } from "../activity/useActivity";
import type { ActivityTone } from "../activity/useActivity";
import { errorPresets, variantShowcases } from "./errorExamples";

type ToastExample = {
  key: string;
  id: string;
  message: string;
  tone: ActivityTone;
};

const toastExamples: ToastExample[] = [
  { key: "raceState", id: ACTIVITY_IDS.raceState, message: ACTIVITY_MESSAGES.raceState, tone: "neutral" },
  { key: "track", id: ACTIVITY_IDS.track, message: ACTIVITY_MESSAGES.track, tone: "neutral" },
  { key: "retryRaceState", id: ACTIVITY_IDS.retryRaceState, message: ACTIVITY_MESSAGES.retryRaceState, tone: "amber" },
  { key: "retryTrack", id: ACTIVITY_IDS.retryTrack, message: ACTIVITY_MESSAGES.retryTrack, tone: "amber" },
  { key: "socketConnecting", id: ACTIVITY_IDS.socket, message: ACTIVITY_MESSAGES.socketConnecting, tone: "neutral" },
  { key: "socketReconnecting", id: ACTIVITY_IDS.socket, message: ACTIVITY_MESSAGES.socketReconnecting, tone: "amber" },
  { key: "snapshotRefresh", id: ACTIVITY_IDS.snapshotRefresh, message: ACTIVITY_MESSAGES.snapshotRefresh, tone: "neutral" },
  { key: "snapshotStale", id: ACTIVITY_IDS.snapshotRefresh, message: ACTIVITY_MESSAGES.snapshotStale, tone: "amber" },
  { key: "replaySessions", id: ACTIVITY_IDS.replaySessions, message: ACTIVITY_MESSAGES.replaySessions, tone: "neutral" },
  { key: "replayDownload", id: ACTIVITY_IDS.replayDownload, message: ACTIVITY_MESSAGES.replayDownload, tone: "neutral" },
];

const toastExampleByKey = new Map(toastExamples.map((example) => [example.key, example]));

type LoadingVariant = "connecting" | "loading";

const loadingVariants: { key: LoadingVariant; label: string }[] = [
  { key: "connecting", label: "Connecting to server" },
  { key: "loading", label: "Loading data" },
];

export function StateWorkbench() {
  const activity = useActivity();
  const [selectedErrorKey, setSelectedErrorKey] = useState(errorPresets[0].key);
  const [showAllErrors, setShowAllErrors] = useState(false);
  const [showRetry, setShowRetry] = useState(true);
  const [selectedLoading, setSelectedLoading] = useState<LoadingVariant>("connecting");
  const [showAllLoading, setShowAllLoading] = useState(false);
  const [activeToastKeys, setActiveToastKeys] = useState<string[]>([]);

  const selectedError = errorPresets.find((preset) => preset.key === selectedErrorKey) ?? errorPresets[0];

  useEffect(() => {
    const managedIds = new Set(toastExamples.map((example) => example.id));
    managedIds.forEach((id) => activity.clear(id));
    activeToastKeys.forEach((key) => {
      const example = toastExampleByKey.get(key);
      if (example) {
        activity.set(example.id, example.message, example.tone);
      }
    });
  }, [activeToastKeys, activity]);

  useEffect(() => {
    return () => {
      toastExamples.forEach((example) => activity.clear(example.id));
    };
  }, [activity]);

  const toggleToast = (key: string) => {
    setActiveToastKeys((prev) =>
      prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key],
    );
  };

  const showAllToasts = () => setActiveToastKeys(toastExamples.map((example) => example.key));
  const clearAllToasts = () => setActiveToastKeys([]);
  const replayToasts = () => {
    const current = activeToastKeys;
    setActiveToastKeys([]);
    window.setTimeout(() => setActiveToastKeys(current), 260);
  };

  return (
    <main className="dashboard-shell">
      <div className="state-workbench">
        <div className="state-workbench-header">
          <div>
            <div role="heading" aria-level={1} className="state-workbench-heading">
              UI State Workbench
            </div>
            <div className="state-workbench-intro">
              Edit state-screens.css or activity-toasts.css and watch these real components update via HMR.
            </div>
          </div>
          <Link to="/test" className="state-workbench-back">
            Back to test index
          </Link>
        </div>

        <ActivityToastStack />

        <section className="state-workbench-section" aria-labelledby="workbench-errors">
          <div id="workbench-errors" role="heading" aria-level={2} className="state-workbench-section-title">
            Error screens
          </div>
          <div className="state-workbench-controls" role="group" aria-label="Error examples">
            {errorPresets.map((preset) => (
              <button
                key={preset.key}
                type="button"
                className={`state-workbench-button ${!showAllErrors && preset.key === selectedErrorKey ? "state-workbench-button--active" : ""}`}
                aria-pressed={!showAllErrors && preset.key === selectedErrorKey}
                onClick={() => {
                  setSelectedErrorKey(preset.key);
                  setShowAllErrors(false);
                }}
              >
                {preset.label}
              </button>
            ))}
            <button
              type="button"
              className={`state-workbench-button ${showAllErrors ? "state-workbench-button--active" : ""}`}
              aria-pressed={showAllErrors}
              onClick={() => setShowAllErrors((value) => !value)}
            >
              Show all
            </button>
          </div>
          <label className="state-workbench-toggle">
            <input
              type="checkbox"
              checked={showRetry}
              onChange={(event) => setShowRetry(event.target.checked)}
            />
            Show retry button
          </label>
          {showAllErrors ? (
            <div className="state-workbench-grid">
              {variantShowcases.map((preset) => (
                <div key={preset.key} className="state-workbench-preview">
                  <ErrorScreen
                    variant={classifyError(preset.error)}
                    error={preset.error}
                    embedded
                    onRetry={showRetry ? () => {} : undefined}
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="state-workbench-preview">
              <ErrorScreen
                variant={classifyError(selectedError.error)}
                error={selectedError.error}
                embedded
                onRetry={showRetry ? () => {} : undefined}
              />
            </div>
          )}
        </section>

        <section className="state-workbench-section" aria-labelledby="workbench-loading">
          <div id="workbench-loading" role="heading" aria-level={2} className="state-workbench-section-title">
            Loading screens
          </div>
          <div className="state-workbench-controls" role="group" aria-label="Loading examples">
            {loadingVariants.map((variant) => (
              <button
                key={variant.key}
                type="button"
                className={`state-workbench-button ${!showAllLoading && selectedLoading === variant.key ? "state-workbench-button--active" : ""}`}
                aria-pressed={!showAllLoading && selectedLoading === variant.key}
                onClick={() => {
                  setSelectedLoading(variant.key);
                  setShowAllLoading(false);
                }}
              >
                {variant.label}
              </button>
            ))}
            <button
              type="button"
              className={`state-workbench-button ${showAllLoading ? "state-workbench-button--active" : ""}`}
              aria-pressed={showAllLoading}
              onClick={() => setShowAllLoading((value) => !value)}
            >
              Show all
            </button>
          </div>
          {showAllLoading ? (
            <div className="state-workbench-grid">
              {loadingVariants.map((variant) => (
                <div key={variant.key} className="state-workbench-preview">
                  <LoadingScreen variant={variant.key} embedded />
                </div>
              ))}
            </div>
          ) : (
            <div className="state-workbench-preview">
              <LoadingScreen variant={selectedLoading} embedded />
            </div>
          )}
        </section>

        <section className="state-workbench-section" aria-labelledby="workbench-toasts">
          <div id="workbench-toasts" role="heading" aria-level={2} className="state-workbench-section-title">
            Activity / loading toasts
          </div>
          <div className="state-workbench-note">
            Toasts render in the real ActivityToastStack fixed below the header and stay visible until cleared.
          </div>
          <div className="state-workbench-controls" role="group" aria-label="Toast examples">
            {toastExamples.map((example) => (
              <button
                key={example.key}
                type="button"
                className={`state-workbench-button ${activeToastKeys.includes(example.key) ? "state-workbench-button--active" : ""}`}
                aria-pressed={activeToastKeys.includes(example.key)}
                onClick={() => toggleToast(example.key)}
              >
                <span>{example.message}</span>
                <span className={`state-workbench-tag state-workbench-tag--${example.tone}`}>{example.tone}</span>
              </button>
            ))}
          </div>
          <div className="state-workbench-controls" role="group" aria-label="Toast actions">
            <button type="button" className="state-workbench-button" onClick={showAllToasts}>
              Show all
            </button>
            <button type="button" className="state-workbench-button" onClick={clearAllToasts}>
              Clear all
            </button>
            <button type="button" className="state-workbench-button" onClick={replayToasts}>
              Replay animation
            </button>
          </div>
        </section>
      </div>
    </main>
  );
}
