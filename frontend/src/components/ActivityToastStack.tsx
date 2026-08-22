import { useCallback, useEffect, useState } from "react";
import { useActivityOperations } from "../features/activity/useActivity";
import type { ActivityOperation } from "../features/activity/useActivity";

const EXIT_MS = 180;

type ToastItem = ActivityOperation & { leaving: boolean };

export function ActivityToastStack() {
  const operations = useActivityOperations();
  const [items, setItems] = useState<ToastItem[]>([]);

  useEffect(() => {
    const currentIds = new Set(operations.map((operation) => operation.id));
    setItems((prev) => {
      const next: ToastItem[] = [];
      for (const operation of operations) {
        next.push({ ...operation, leaving: false });
      }
      for (const item of prev) {
        if (!currentIds.has(item.id)) {
          next.push({ ...item, leaving: true });
        }
      }
      return next;
    });
  }, [operations]);

  const handleExited = useCallback((id: string) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  if (items.length === 0) {
    return null;
  }

  return (
    <div className="activity-toasts" role="status" aria-live="polite">
      {items.map((item) => (
        <ActivityToast key={item.id} item={item} onExited={handleExited} />
      ))}
    </div>
  );
}

function ActivityToast({ item, onExited }: { item: ToastItem; onExited: (id: string) => void }) {
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setShown(true));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!item.leaving) {
      return;
    }
    const timer = window.setTimeout(() => onExited(item.id), EXIT_MS);
    return () => window.clearTimeout(timer);
  }, [item.leaving, item.id, onExited]);

  const className = [
    "activity-toast",
    item.tone === "amber" ? "activity-toast--amber" : "activity-toast--neutral",
    shown ? "activity-toast--shown" : "",
    item.leaving ? "activity-toast--leaving" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={className}>
      <span className="activity-toast-spinner" aria-hidden="true" />
      <span className="activity-toast-message">{item.message}</span>
    </div>
  );
}
