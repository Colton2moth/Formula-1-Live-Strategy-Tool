import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import App from "./App";
import { ApiError } from "./api/raceState";
import { ErrorScreen } from "./components/ErrorScreen";
import { LoadingScreen } from "./components/LoadingScreen";
import { ActivityProvider } from "./features/activity/useActivity";
import { ReplayPage } from "./features/replay/ReplayPage";
import { TestIndex } from "./features/test-screens/TestIndex";
import { TrackMapPreviews } from "./features/test-screens/TrackMapPreviews";
import "./index.css";
import "./styles/shared.css";
import "./styles/race-header.css";
import "./styles/track-map.css";
import "./styles/track-map-previews.css";
import "./styles/leaderboard.css";
import "./styles/strategy-panel.css";
import "./styles/state-screens.css";
import "./styles/activity-toasts.css";
import "./features/replay/replay.css";

const unavailableExample = new ApiError({
  type: "network",
  method: "GET",
  path: "/api/track",
  message: "Failed to fetch",
});

const serverErrorExample = new ApiError({
  type: "http",
  method: "GET",
  path: "/api/race-state",
  message: "Request failed: 500",
  status: 500,
  statusText: "Internal Server Error",
  serverDetail: "Failed to build race snapshot",
  attempts: 4,
});

const invalidDataExample = new ApiError({
  type: "invalid-data",
  method: "GET",
  path: "/api/race-state",
  message: "Race state response did not match the expected shape.",
  status: 200,
  statusText: "OK",
});

const timeoutExample = new ApiError({
  type: "timeout",
  method: "GET",
  path: "/api/race-state",
  message: "The request did not complete within the configured time limit.",
});

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ActivityProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/replay" element={<ReplayPage />} />
          <Route path="/test" element={<TestIndex />} />
          <Route path="/test/maps" element={<TrackMapPreviews />} />
          <Route path="/test/loading/connecting" element={<LoadingScreen variant="connecting" />} />
          <Route path="/test/loading/data" element={<LoadingScreen variant="loading" />} />
          <Route path="/test/error/unavailable" element={<ErrorScreen variant="unavailable" error={unavailableExample} />} />
          <Route path="/test/error/server-error" element={<ErrorScreen variant="server-error" error={serverErrorExample} />} />
          <Route path="/test/error/invalid-data" element={<ErrorScreen variant="invalid-data" error={invalidDataExample} />} />
          <Route path="/test/error/timeout" element={<ErrorScreen variant="timeout" error={timeoutExample} />} />
        </Routes>
      </BrowserRouter>
    </ActivityProvider>
  </React.StrictMode>,
);
