import { useEffect, useRef } from "react";
import { STEPS } from "./steps";
import { useActiveStep } from "./useActiveStep";

interface Props {
  reducedMotion: boolean;
}

/**
 * Pinned illustration with scrolling text steps. The text is the content; the illustration
 * is decorative (aria-hidden) and only reflects the step being read. With reduced motion or
 * without IntersectionObserver every step is shown in full and the illustration shows the
 * finished loaf, with no animation.
 */
export function ScrollStory({ reducedMotion }: Props) {
  const container = useRef<HTMLOListElement>(null);
  const figure = useRef<HTMLDivElement>(null);
  const active = useActiveStep(container, STEPS.length, !reducedMotion);
  const shown = active < 0 ? STEPS.length - 1 : active;

  useEffect(() => {
    const el = figure.current;
    if (!el || reducedMotion || typeof el.animate !== "function") return;
    const animation = el.animate(
      [{ opacity: 0.35, transform: "scale(0.96)" }, { opacity: 1, transform: "scale(1)" }],
      { duration: 280, easing: "cubic-bezier(0.2, 0, 0, 1)" },
    );
    return () => animation.cancel();
  }, [shown, reducedMotion]);

  return (
    <div className={`story ${active < 0 ? "story--static" : "story--live"}`}>
      <div className="story__visual" aria-hidden="true">
        <div className="story__figure" ref={figure} data-stage={STEPS[shown].id}>
          <span className="story__shape" />
          <span className="story__caption">{STEPS[shown].title}</span>
        </div>
      </div>
      <ol className="story__steps" ref={container}>
        {STEPS.map((step, i) => (
          <li key={step.id} data-step={i} className={i === active ? "is-active" : undefined}
              aria-current={i === active ? "step" : undefined}>
            <p className="story__time">{step.time}</p>
            <h2>{step.title}</h2>
            <p>{step.body}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
