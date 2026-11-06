import { useEffect, useState, type RefObject } from "react";

/**
 * Index of the step nearest the middle of the viewport, observed with IntersectionObserver.
 * Returns -1 when observation is off (reduced motion or no IntersectionObserver): every step
 * is then shown in its finished state. The observer is disconnected on unmount and whenever
 * the inputs change, so remounts (React StrictMode, route changes) never leave observers behind.
 */
export function useActiveStep(container: RefObject<HTMLElement | null>, count: number, enabled: boolean): number {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const root = container.current;
    if (!enabled || !root || typeof IntersectionObserver === "undefined") return;
    const steps = Array.from(root.querySelectorAll<HTMLElement>("[data-step]"));
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive(Number((entry.target as HTMLElement).dataset.step));
        }
      },
      { rootMargin: "-45% 0px -45% 0px" },
    );
    steps.forEach((step) => observer.observe(step));
    trackObservers(+1);
    return () => {
      observer.disconnect();
      trackObservers(-1);
    };
  }, [container, count, enabled]);

  return enabled && typeof IntersectionObserver !== "undefined" ? active : -1;
}

// Fixture instrumentation: the number of live observers, read by the browser verification.
function trackObservers(delta: number): void {
  const el = document.documentElement;
  el.dataset.storyObservers = String(Number(el.dataset.storyObservers ?? 0) + delta);
}
