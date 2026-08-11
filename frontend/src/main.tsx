import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import App from "./App";
import { ErrorScreen } from "./components/ErrorScreen";
import { LoadingScreen } from "./components/LoadingScreen";
import { TestIndex } from "./features/test-screens/TestIndex";
import "./index.css";
import "./styles/shared.css";
import "./styles/race-header.css";
import "./styles/track-map.css";
import "./styles/leaderboard.css";
import "./styles/strategy-panel.css";
import "./styles/state-screens.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/test" element={<TestIndex />} />
        <Route path="/test/loading/connecting" element={<LoadingScreen variant="connecting" />} />
        <Route path="/test/loading/data" element={<LoadingScreen variant="loading" />} />
        <Route path="/test/error/unavailable" element={<ErrorScreen variant="unavailable" />} />
        <Route path="/test/error/server-error" element={<ErrorScreen variant="server-error" />} />
        <Route path="/test/error/invalid-data" element={<ErrorScreen variant="invalid-data" />} />
        <Route path="/test/error/timeout" element={<ErrorScreen variant="timeout" />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
