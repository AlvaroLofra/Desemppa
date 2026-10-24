/** @type {import('tailwindcss').Config} */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: token("surface"),
        "surface-2": token("surface-2"),
        "surface-3": token("surface-3"),
        outline: token("outline"),
        ink: token("text"),
        "ink-2": token("text-2"),
        "ink-3": token("text-3"),
        accent: token("accent"),
        "on-accent": token("on-accent"),
        "accent-container": token("accent-container"),
        "on-accent-container": token("on-accent-container"),
        danger: token("danger"),
        "danger-container": token("danger-container"),
        warning: token("warning"),
        "warning-container": token("warning-container"),
        success: token("success"),
        highlight: token("highlight"),
      },
      boxShadow: { float: "var(--shadow)" },
      fontFamily: {
        sans: ["'Inter Variable'", "system-ui", "sans-serif"],
        serif: ["'Source Serif 4'", "Georgia", "serif"],
      },
    },
  },
  plugins: [],
};
