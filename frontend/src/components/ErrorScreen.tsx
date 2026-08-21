import { useState } from "react";
import type { FC } from "react";
import type { ApiError, ApiErrorType } from "../api/raceState";

export type ErrorVariant = "unavailable" | "server-error" | "invalid-data" | "timeout";

const errorContent: Record<
  ErrorVariant,
  { icon: string; title: string; message: string; help: string }
> = {
  unavailable: {
    icon: "cloud_off",
    title: "API unavailable",
    message: "The race server could not be reached.",
    help: "Check that the backend is running and accessible at the configured API URL.",
  },
  "server-error": {
    icon: "error",
    title: "Server error",
    message: "The API returned an unexpected error.",
    help: "This may be a temporary issue with the data provider. Try again in a moment.",
  },
  "invalid-data": {
    icon: "data_thresholding",
    title: "Invalid data",
    message: "The API response did not match the expected format.",
    help: "This could indicate a version mismatch between the frontend and backend.",
  },
  timeout: {
    icon: "hourglass_empty",
    title: "Request timed out",
    message: "The API did not respond within the expected time window.",
    help: "The server may be overloaded or a network issue may be slowing the connection.",
  },
};

const typeLabel: Record<ApiErrorType, string> = {
  network: "API unavailable",
  http: "Server error",
  "invalid-data": "Invalid data",
  timeout: "Request timed out",
  unknown: "Unknown error",
};

type DetailRow = { label: string; value: string };

function detailRows(error: ApiError): DetailRow[] {
  const rows: DetailRow[] = [{ label: "Type", value: typeLabel[error.type] }];

  if (error.status !== null) {
    const status = error.statusText ? `${error.status} ${error.statusText}` : String(error.status);
    rows.push({ label: "Status", value: status });
  }

  const requestParts: string[] = [];
  if (error.method) requestParts.push(error.method);
  if (error.path) requestParts.push(error.path);
  if (requestParts.length > 0) {
    rows.push({ label: "Request", value: requestParts.join(" ") });
  }

  rows.push({ label: "Message", value: error.message });

  if (error.serverDetail) {
    rows.push({ label: "Server detail", value: error.serverDetail });
  }

  if (error.attempts > 1) {
    rows.push({ label: "Attempts", value: String(error.attempts) });
  }

  rows.push({ label: "Time", value: error.timestamp });
  return rows;
}

function buildCopyText(error: ApiError): string {
  return [
    "F1 Strategy Tool Error",
    ...detailRows(error).map(({ label, value }) => `${label}: ${value}`),
  ].join("\n");
}

export const ErrorScreen: FC<{
  variant: ErrorVariant;
  message?: string;
  error?: ApiError;
  embedded?: boolean;
}> = ({ variant, message, error, embedded = false }) => {
  const { icon, title, message: defaultMessage, help } = errorContent[variant];
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!error || !navigator.clipboard) return;
    navigator.clipboard.writeText(buildCopyText(error)).then(
      () => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      },
      () => {
        // Clipboard write failed; never surface a secondary error.
      },
    );
  };

  const content = (
    <div className="state-screen">
      <span className="material-symbols-rounded state-screen-icon state-screen-icon--error" aria-hidden="true">
        {icon}
      </span>
      <div>
        <div role="heading" aria-level={1} className="state-screen-title">
          {title}
        </div>
        <div className="state-screen-message">{message ?? defaultMessage}</div>
        <div className="state-screen-help">{help}</div>
      </div>
      {error ? (
        <details className="error-details">
          <summary className="error-details-summary">
            <span className="material-symbols-rounded error-details-chevron" aria-hidden="true">
              expand_more
            </span>
            Error details
          </summary>
          <div className="error-details-panel">
            <div className="error-details-toolbar">
              <button type="button" className="error-details-copy" onClick={handleCopy}>
                {copied ? "Copied" : "Copy error details"}
              </button>
            </div>
            <dl className="error-details-list">
              {detailRows(error).map(({ label, value }) => (
                <div className="error-details-row" key={label}>
                  <dt className="error-details-label">{label}</dt>
                  <dd className="error-details-value">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </details>
      ) : null}
    </div>
  );

  if (embedded) {
    return content;
  }

  return <main className="dashboard-shell">{content}</main>;
};
