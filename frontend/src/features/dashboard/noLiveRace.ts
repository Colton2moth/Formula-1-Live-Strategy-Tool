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
