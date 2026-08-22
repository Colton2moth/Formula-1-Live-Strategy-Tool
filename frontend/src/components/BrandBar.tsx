import { useLayoutEffect, useRef } from "react";
import { Link } from "react-router-dom";

type BrandBarProps = {
  replayMode?: boolean;
};

export function BrandBar({ replayMode = false }: BrandBarProps) {
  const headerRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const header = headerRef.current;
    if (!header) return;

    const updateHeaderOffset = () => {
      document.documentElement.style.setProperty(
        "--header-offset",
        `${header.getBoundingClientRect().height}px`,
      );
    };

    updateHeaderOffset();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(updateHeaderOffset);
    observer?.observe(header);

    return () => {
      observer?.disconnect();
      document.documentElement.style.removeProperty("--header-offset");
    };
  }, []);

  return (
    <div ref={headerRef} className="dashboard-brand">
      <div role="heading" aria-level={1} className="dashboard-brand-title">
        PitPit
      </div>
      <div className="dashboard-brand-subtitle">F1 Live Strategy Tool</div>
      <nav className="dashboard-brand-nav" aria-label="Primary navigation">
        {replayMode ? (
          <Link className="dashboard-brand-nav-link" to="/">
            Live Race
          </Link>
        ) : (
          <Link className="dashboard-brand-nav-link" to="/replay">
            Race Replay
          </Link>
        )}
      </nav>
    </div>
  );
}
