import { Link } from "react-router-dom";

type NoLiveRaceModalProps = {
  checking: boolean;
  onCheckAgain: () => void;
};

export function NoLiveRaceModal({ checking, onCheckAgain }: NoLiveRaceModalProps) {
  return (
    <div className="no-live-race-backdrop">
      <div
        className="no-live-race-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="no-live-race-title"
        aria-describedby="no-live-race-description"
      >
        <span className="material-symbols-rounded no-live-race-icon" aria-hidden="true">
          sports_score
        </span>
        <div id="no-live-race-title" className="no-live-race-title" role="heading" aria-level={2}>
          No Live Race
        </div>
        <div id="no-live-race-description" className="no-live-race-description">
          Currently there is no Live Formula 1 race.
        </div>
        <div className="no-live-race-supporting-copy">
          Want to explore PitPit while you wait? Watch a previous Grand Prix in Replay Mode.
        </div>
        <Link className="no-live-race-replay-link" to="/replay" autoFocus>
          <span className="material-symbols-rounded" aria-hidden="true">arrow_outward</span>
          <span>View Race Replays</span>
        </Link>
        <button
          type="button"
          className="no-live-race-check-button"
          onClick={onCheckAgain}
          disabled={checking}
        >
          <span className="material-symbols-rounded" aria-hidden="true">refresh</span>
          <span>{checking ? "Checking…" : "Check Again For Live Race"}</span>
        </button>
      </div>
    </div>
  );
}
