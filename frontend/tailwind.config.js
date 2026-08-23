/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#102A2E",
          soft: "#2A4549",
          muted: "#5C7377",
        },
        paper: {
          DEFAULT: "#F4F6F3",
          raised: "#FBFCFA",
          line: "#D5DDD7",
        },
        signal: {
          DEFAULT: "#1F6F5B",
          deep: "#164F41",
          wash: "#E4F1EC",
        },
        warn: {
          DEFAULT: "#B45309",
          wash: "#FEF3E7",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        desk: "0 1px 0 rgba(16,42,46,0.06), 0 18px 40px -28px rgba(16,42,46,0.35)",
      },
      keyframes: {
        "rise-in": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "rule-draw": {
          from: { transform: "scaleX(0)" },
          to: { transform: "scaleX(1)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "0.35" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        "rise-in": "rise-in 0.45s ease-out both",
        "fade-in": "fade-in 0.5s ease-out both",
        "rule-draw": "rule-draw 0.7s ease-out both",
        "pulse-dot": "pulse-dot 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
