/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        teal: {
          950: "#0A2A2B",
          900: "#0E3536",
          800: "#134646",
          700: "#1A5858",
          600: "#237070",
          500: "#2E8888",
          400: "#5CACAB",
        },
        paper: "#FFFFFF",
        bone: "#F6F3EC",
        ink: "#16211F",
        subink: "#5B6E69",
        line: "#E1DCCF",
        tier1: "#C0392B",
        tier2: "#D9762A",
        tier3: "#CC9A2E",
        tier4: "#2E7D6B",
        tier5: "#5E8B82",
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'IBM Plex Sans'", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(10,42,43,0.06), 0 1px 12px rgba(10,42,43,0.05)",
      },
      keyframes: {
        pulse_border: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(192,57,43,0.55)" },
          "50%": { boxShadow: "0 0 0 6px rgba(192,57,43,0.0)" },
        },
      },
      animation: {
        alert: "pulse_border 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
}
