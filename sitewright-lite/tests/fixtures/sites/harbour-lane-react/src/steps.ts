export interface Step {
  id: string;
  title: string;
  time: string;
  body: string;
}

// [fixture] content for a fictional bakery.
export const STEPS: Step[] = [
  { id: "feed", title: "Feed the starter", time: "Day 1, 8pm",
    body: "The starter gets flour and water the night before, so it is at its liveliest by morning." },
  { id: "mix", title: "Mix and rest", time: "Day 2, 7am",
    body: "Flour, water, starter and salt are mixed, then folded four times over the next three hours." },
  { id: "shape", title: "Shape and prove overnight", time: "Day 2, 4pm",
    body: "Each loaf is shaped by hand and proves slowly in the cold room until the next morning." },
  { id: "bake", title: "Bake at dawn", time: "Day 3, 5am",
    body: "Loaves bake in a steam-filled oven for forty minutes and are on the shelf by opening time." },
];
