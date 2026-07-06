import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import "./styles/shared.css";
import "./styles/race-header.css";
import "./styles/track-map.css";
import "./styles/leaderboard.css";
import "./styles/strategy-panel.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
