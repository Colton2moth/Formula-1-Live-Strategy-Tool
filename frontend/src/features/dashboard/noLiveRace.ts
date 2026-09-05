import type { LiveSocketStatus } from "../../api/liveSocket";

export type SessionIdentity = {
  meeting_name: string;
  session_name: string;
  session_status: string;
};

export function isActiveSessionStatus(status: string): boolean {
  return status.trim().toLowerCase() === "active";
}

export function noLiveConditionKey(session: SessionIdentity): string {
  const status = session.session_status.trim().toLowerCase();
  return `${session.meeting_name}|${session.session_name}|${status}`;
}

export function shouldShowNoLiveRaceModal(opts: {
  isLiveSource: boolean;
  session: SessionIdentity;
  dismissedKey: string | null;
}): boolean {
  if (!opts.isLiveSource) {
    return false;
  }
  if (isActiveSessionStatus(opts.session.session_status)) {
    return false;
  }
  return opts.dismissedKey !== noLiveConditionKey(opts.session);
}

export type SessionStatusChip = {
  label: string;
  tone: "green" | "amber" | "neutral";
};

const CONNECTION_STATUS: Record<LiveSocketStatus, SessionStatusChip> = {
  connecting: { label: "Connecting", tone: "neutral" },
  open: { label: "Live", tone: "green" },
  reconnecting: { label: "Reconnecting", tone: "amber" },
};

const NO_LIVE_SESSION: SessionStatusChip = { label: "No Live Session", tone: "neutral" };

export function resolveSessionStatusChip(opts: {
  isLiveSource: boolean;
  connectionStatus: LiveSocketStatus;
  session: SessionIdentity | null;
}): SessionStatusChip {
  // Replay keeps its own connection status and never reports a live-session
  // state, so it can never surface "No Live Session".
  if (!opts.isLiveSource) {
    return CONNECTION_STATUS[opts.connectionStatus];
  }
  // While the socket is still establishing (or no authoritative session has
  // loaded yet), keep the loading/connecting label.
  if (opts.connectionStatus === "connecting" || opts.session === null) {
    return CONNECTION_STATUS[opts.connectionStatus];
  }
  // An active session (Race, Qualifying, Sprint, Practice) keeps the
  // connection status, so a reconnect with last-valid active data shows
  // "Reconnecting" rather than "No Live Session".
  if (isActiveSessionStatus(opts.session.session_status)) {
    return CONNECTION_STATUS[opts.connectionStatus];
  }
  return NO_LIVE_SESSION;
}
