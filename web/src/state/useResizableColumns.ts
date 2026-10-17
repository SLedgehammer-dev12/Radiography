import { useCallback, useRef, useState } from "react";

const STORAGE_KEY = "radiography_col_widths_v1";

/** Default column width ratios: Left (Inputs) 28%, Middle (Outputs) 32%, Right (3D View) 40% */
export const DEFAULT_COL_WIDTHS: [number, number, number] = [28, 32, 40];

function loadSavedWidths(): [number, number, number] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_COL_WIDTHS;
    const parsed = JSON.parse(raw) as number[];
    if (
      Array.isArray(parsed) &&
      parsed.length === 3 &&
      parsed.every(
        (n) => typeof n === "number" && !Number.isNaN(n) && n >= 15 && n <= 75,
      )
    ) {
      const sum = parsed[0] + parsed[1] + parsed[2];
      if (Math.abs(sum - 100) <= 2) {
        return [parsed[0], parsed[1], parsed[2]];
      }
    }
  } catch {
    // fallback to defaults on any storage error
  }
  return DEFAULT_COL_WIDTHS;
}

/**
 * Hook for managing adjustable 3-column layout widths with drag handles,
 * keyboard accessibility, and persistence to localStorage.
 */
export function useResizableColumns() {
  const [widths, setWidths] = useState<[number, number, number]>(loadSavedWidths);
  const [activeSplitter, setActiveSplitter] = useState<0 | 1 | null>(null);
  const layoutRef = useRef<HTMLElement | null>(null);

  const resetWidths = useCallback(() => {
    setWidths(DEFAULT_COL_WIDTHS);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_COL_WIDTHS));
    } catch {
      // ignore storage failure
    }
  }, []);

  const startResize = useCallback(
    (index: 0 | 1, event: React.PointerEvent) => {
      // Only handle primary left click
      if (event.button !== 0) return;
      event.preventDefault();

      const layout = layoutRef.current;
      if (!layout) return;

      const layoutRect = layout.getBoundingClientRect();
      const layoutWidth = layoutRect.width;
      if (layoutWidth < 700) return; // Do not resize on mobile or tablet layouts

      const startX = event.clientX;
      const initialWidths = [...widths] as [number, number, number];

      setActiveSplitter(index);
      document.body.classList.add("resizing-columns");

      let currentWidths = initialWidths;

      const handlePointerMove = (moveEvent: PointerEvent) => {
        const deltaX = moveEvent.clientX - startX;
        const deltaPct = (deltaX / layoutWidth) * 100;

        if (index === 0) {
          // Adjust boundary between Column 0 (Inputs) and Column 1 (Outputs)
          const combined = initialWidths[0] + initialWidths[1];
          let new0 = Math.max(20, Math.min(45, initialWidths[0] + deltaPct));
          let new1 = combined - new0;
          if (new1 < 20) {
            new1 = 20;
            new0 = combined - 20;
          }
          currentWidths = [
            Number(new0.toFixed(2)),
            Number(new1.toFixed(2)),
            initialWidths[2],
          ];
        } else {
          // Adjust boundary between Column 1 (Outputs) and Column 2 (3D View)
          const combined = initialWidths[1] + initialWidths[2];
          // Dragging right reduces Column 2, dragging left expands Column 2
          let new2 = Math.max(25, Math.min(60, initialWidths[2] - deltaPct));
          let new1 = combined - new2;
          if (new1 < 20) {
            new1 = 20;
            new2 = combined - 20;
          }
          currentWidths = [
            initialWidths[0],
            Number(new1.toFixed(2)),
            Number(new2.toFixed(2)),
          ];
        }

        setWidths(currentWidths);
      };

      const handlePointerUp = () => {
        setActiveSplitter(null);
        document.body.classList.remove("resizing-columns");
        window.removeEventListener("pointermove", handlePointerMove);
        window.removeEventListener("pointerup", handlePointerUp);
        window.removeEventListener("pointercancel", handlePointerUp);

        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(currentWidths));
        } catch {
          // ignore
        }
      };

      window.addEventListener("pointermove", handlePointerMove);
      window.addEventListener("pointerup", handlePointerUp);
      window.addEventListener("pointercancel", handlePointerUp);
    },
    [widths],
  );

  const handleResizerKeyDown = useCallback(
    (index: 0 | 1, event: React.KeyboardEvent) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        resetWidths();
        return;
      }
      const step = event.shiftKey ? 3 : 1;
      let deltaPct = 0;
      if (event.key === "ArrowLeft") {
        deltaPct = -step;
      } else if (event.key === "ArrowRight") {
        deltaPct = step;
      } else {
        return;
      }
      event.preventDefault();

      setWidths((prev) => {
        let updated = [...prev] as [number, number, number];
        if (index === 0) {
          const combined = prev[0] + prev[1];
          let new0 = Math.max(20, Math.min(45, prev[0] + deltaPct));
          let new1 = combined - new0;
          if (new1 < 20) {
            new1 = 20;
            new0 = combined - 20;
          }
          updated = [
            Number(new0.toFixed(2)),
            Number(new1.toFixed(2)),
            prev[2],
          ];
        } else {
          const combined = prev[1] + prev[2];
          let new2 = Math.max(25, Math.min(60, prev[2] - deltaPct));
          let new1 = combined - new2;
          if (new1 < 20) {
            new1 = 20;
            new2 = combined - 20;
          }
          updated = [
            prev[0],
            Number(new1.toFixed(2)),
            Number(new2.toFixed(2)),
          ];
        }
        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        } catch {
          // ignore
        }
        return updated;
      });
    },
    [resetWidths],
  );

  return {
    widths,
    activeSplitter,
    layoutRef,
    startResize,
    resetWidths,
    handleResizerKeyDown,
  };
}
