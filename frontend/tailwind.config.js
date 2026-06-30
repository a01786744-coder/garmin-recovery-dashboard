// `neutral` is redefined as CSS-variable-backed so every text-neutral-*/bg-neutral-*
// utility is themed by the [data-theme] tokens in index.css (dark = original
// Tailwind neutrals, light = flipped). `line` backs hairline borders/overlays
// that were previously literal white (e.g. border-line/10, bg-line/5).
const shades = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];
const neutral = Object.fromEntries(
  shades.map((s) => [s, `rgb(var(--neutral-${s}) / <alpha-value>)`])
);

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        neutral,
        line: "rgb(var(--line) / <alpha-value>)",
      },
    },
  },
  plugins: [],
};
