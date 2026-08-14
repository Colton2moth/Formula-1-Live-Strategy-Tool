import type { FC } from "react";

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

export const ErrorScreen: FC<{
  variant: ErrorVariant;
  message?: string;
}> = ({ variant, message }) => {
  const { icon, title, message: defaultMessage, help } = errorContent[variant];

  return (
    <main className="dashboard-shell">
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
      </div>
    </main>
  );
};
