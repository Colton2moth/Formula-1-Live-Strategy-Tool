import { Link } from "react-router-dom";
import type { FC } from "react";

const loadingStates = [
  { path: "/test/loading/connecting", label: "Connecting to server", code: "loading:connecting" },
  { path: "/test/loading/data", label: "Loading data", code: "loading:loading" },
] as const;

const errorStates = [
  { path: "/test/error/unavailable", label: "API unavailable", code: "error:unavailable" },
  { path: "/test/error/server-error", label: "Server error", code: "error:server-error" },
  { path: "/test/error/invalid-data", label: "Invalid data format", code: "error:invalid-data" },
  { path: "/test/error/timeout", label: "Request timeout", code: "error:timeout" },
] as const;

const utilityPages = [
  { path: "/test/maps", label: "Track map previews", code: "track-map-previews" },
] as const;

export const TestIndex: FC = () => {
  return (
    <main className="dashboard-shell">
      <div className="test-index">
        <div role="heading" aria-level={1} className="test-index-heading">
          State Screen Tests
        </div>

        <div className="test-index-group">
          <div className="test-index-group-title">Loading States</div>
          <div className="test-index-links">
            {loadingStates.map(({ path, label, code }) => (
              <Link key={path} to={path} className="test-index-link">
                <span>{label}</span>
                <span className="test-index-link-code">{code}</span>
              </Link>
            ))}
          </div>
        </div>

        <div className="test-index-group">
          <div className="test-index-group-title">Error States</div>
          <div className="test-index-links">
            {errorStates.map(({ path, label, code }) => (
              <Link key={path} to={path} className="test-index-link">
                <span>{label}</span>
                <span className="test-index-link-code">{code}</span>
              </Link>
            ))}
          </div>
        </div>

        <div className="test-index-group">
          <div className="test-index-group-title">Utilities</div>
          <div className="test-index-links">
            {utilityPages.map(({ path, label, code }) => (
              <Link key={path} to={path} className="test-index-link">
                <span>{label}</span>
                <span className="test-index-link-code">{code}</span>
              </Link>
            ))}
          </div>
        </div>

        <Link to="/" className="test-index-link">
          <span>Back to dashboard</span>
          <span className="test-index-link-code">/</span>
        </Link>
      </div>
    </main>
  );
};
