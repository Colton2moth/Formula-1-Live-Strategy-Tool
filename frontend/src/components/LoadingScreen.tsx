import type { FC } from "react";

export type LoadingVariant = "connecting" | "loading";

const loadingContent: Record<LoadingVariant, { title: string; message: string }> = {
  connecting: {
    title: "Connecting to race server",
    message: "Establishing connection to the live timing API.",
  },
  loading: {
    title: "Loading race data",
    message: "Fetching session, drivers, and track data.",
  },
};

export const LoadingScreen: FC<{ variant: LoadingVariant }> = ({ variant }) => {
  const { title, message } = loadingContent[variant];

  return (
    <main className="dashboard-shell">
      <div className="state-screen">
        <div className="loading-spinner" aria-label="Loading">
          <div className="loading-dot" />
          <div className="loading-dot" />
          <div className="loading-dot" />
        </div>
        <div>
          <div role="heading" aria-level={1} className="state-screen-title">
            {title}
          </div>
          <div className="state-screen-message">{message}</div>
        </div>
      </div>
    </main>
  );
};
