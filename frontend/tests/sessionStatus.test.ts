import { test } from "node:test";
import assert from "node:assert/strict";

import {
  isActiveSessionStatus,
  resolveSessionStatusChip,
} from "../src/features/dashboard/noLiveRace.ts";

function session(status: string, name = "Race") {
  return { meeting_name: "Test Grand Prix", session_name: name, session_status: status };
}

function chip(status: string, name = "Race", connectionStatus = "open", isLiveSource = true) {
  return resolveSessionStatusChip({
    isLiveSource,
    connectionStatus,
    session: session(status, name),
  });
}

const LIVE = { label: "Live", tone: "green" };
const NO_LIVE = { label: "No Live Session", tone: "neutral" };
const CONNECTING = { label: "Connecting", tone: "neutral" };
const RECONNECTING = { label: "Reconnecting", tone: "amber" };

test("active sessions resolve to the live/connected status regardless of session name", () => {
  assert.deepEqual(chip("active", "Race"), LIVE);
  assert.deepEqual(chip("active", "Qualifying"), LIVE);
  assert.deepEqual(chip("active", "Sprint"), LIVE);
  assert.deepEqual(chip("active", "Practice"), LIVE);
});

test("inactive sessions resolve to No Live Session", () => {
  assert.deepEqual(chip("upcoming"), NO_LIVE);
  assert.deepEqual(chip("completed"), NO_LIVE);
  assert.deepEqual(chip("cancelled"), NO_LIVE);
});

test("session liveness never comes from session_name", () => {
  // A "Race" that has completed is still not live.
  assert.deepEqual(chip("completed", "Race"), NO_LIVE);
  // A "Qualifying" that is active is live.
  assert.deepEqual(chip("active", "Qualifying"), LIVE);
});

test("unknown or malformed status is treated as inactive", () => {
  assert.deepEqual(chip(""), NO_LIVE);
  assert.deepEqual(chip("Running"), NO_LIVE);
  assert.deepEqual(chip("unknown"), NO_LIVE);
});

test("status normalization tolerates case and whitespace", () => {
  assert.equal(isActiveSessionStatus("active"), true);
  assert.equal(isActiveSessionStatus(" Active "), true);
  assert.equal(isActiveSessionStatus("ACTIVE"), true);
  assert.equal(isActiveSessionStatus("inactive"), false);
});

test("reconnecting with last-valid active data stays Reconnecting", () => {
  assert.deepEqual(chip("active", "Race", "reconnecting"), RECONNECTING);
});

test("stale-but-active data does not switch to No Live Session", () => {
  // The staleness chip is separate; the primary chip keeps the live status.
  assert.deepEqual(chip("active", "Race", "open"), LIVE);
  assert.deepEqual(chip("active", "Race", "reconnecting"), RECONNECTING);
});

test("initial connecting state before session data exists stays Connecting", () => {
  assert.deepEqual(
    resolveSessionStatusChip({ isLiveSource: true, connectionStatus: "connecting", session: null }),
    CONNECTING,
  );
  assert.deepEqual(chip("active", "Race", "connecting"), CONNECTING);
});

test("replay never shows No Live Session", () => {
  assert.deepEqual(
    resolveSessionStatusChip({
      isLiveSource: false,
      connectionStatus: "open",
      session: session("completed"),
    }),
    LIVE,
  );
  assert.deepEqual(
    resolveSessionStatusChip({
      isLiveSource: false,
      connectionStatus: "open",
      session: session("upcoming"),
    }),
    LIVE,
  );
  assert.deepEqual(
    resolveSessionStatusChip({
      isLiveSource: false,
      connectionStatus: "reconnecting",
      session: session("active"),
    }),
    RECONNECTING,
  );
});
