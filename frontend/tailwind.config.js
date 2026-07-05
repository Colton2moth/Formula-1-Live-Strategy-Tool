/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-app)", "sans-serif"],
      },
      colors: {
        app: {
          bg: "var(--color-bg)",
          panel: "var(--color-panel)",
          panelAlt: "var(--color-panel-alt)",
          line: "var(--color-line)",
          red: "var(--color-f1-red)",
          text: "var(--color-text)",
          muted: "var(--color-muted)",
        },
      },
    },
  },
  plugins: [],
};
