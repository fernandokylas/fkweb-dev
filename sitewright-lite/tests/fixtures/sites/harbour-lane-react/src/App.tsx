import { useState } from "react";
import { ScrollStory } from "./ScrollStory";
import { STEPS } from "./steps";
import { useReducedMotion } from "./useReducedMotion";

export default function App() {
  const reducedMotion = useReducedMotion();
  const [asList, setAsList] = useState(false);

  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="site-header">
        <div className="wrap">
          <a className="brand" href="/">Harbour Lane Bakery</a>
          <nav aria-label="Primary">
            <ul>
              <li><a href="/" aria-current="page">Our sourdough</a></li>
            </ul>
          </nav>
        </div>
      </header>
      <main id="main" className="wrap">
        <h1>How our sourdough is made</h1>
        <p className="lede">Four steps over two days, from feeding the starter to the first loaves out of the oven.</p>
        <p>
          <button type="button" className="button secondary" aria-pressed={asList} onClick={() => setAsList(!asList)}>
            {asList ? "Show as a story" : "Read as a list"}
          </button>
        </p>
        {asList ? (
          <ol className="plain-steps">
            {STEPS.map((step) => (
              <li key={step.id}><strong>{step.title}</strong> ({step.time}). {step.body}</li>
            ))}
          </ol>
        ) : (
          <ScrollStory reducedMotion={reducedMotion} />
        )}
        <p className="after">White sourdough is £4.00 a loaf, baked Tuesday to Sunday.</p>
      </main>
      <footer className="site-footer">
        <div className="wrap">
          <p>Harbour Lane Bakery is a fictional business used to test Sitewright lite [fixture].</p>
        </div>
      </footer>
    </>
  );
}
