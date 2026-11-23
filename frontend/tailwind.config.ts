import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        border: {
          DEFAULT: "var(--border)",
          subtle: "var(--border-subtle)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        metro: {
          navy: "#14213a",
          darkNavy: "#000a21",
          gold: "#98700a",
          goldLight: "#c2931d",
          goldMuted: "#7a5900",
          paper: "#f9f9ff",
          pureWhite: "#ffffff",
          cardLight: "#ecedf7",
          borderLight: "#e2e8f0",
          // Dark mode semantics
          canvasDark: "#0b1019",
          cardDark: "#141c2b",
          borderDark: "#222e42",
          textDarkMuted: "#d8dee9",
        },
        surface: {
          DEFAULT: "var(--surface)",
          lowest: "var(--surface-lowest)",
          low: "var(--surface-low)",
          container: "var(--surface-container)",
          high: "var(--surface-container-high)",
          highest: "var(--surface-container-highest)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          container: "var(--primary-container)",
          onPrimary: "var(--on-primary)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          container: "var(--secondary-container)",
          gold: "#98700a",
        },
      },
      fontFamily: {
        serif: ["var(--font-playfair)", "Playfair Display", "Georgia", "serif"],
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
      },
      spacing: {
        gutter: "1.5rem",
        "gutter-mobile": "1rem",
        margin: "2.5rem",
        "margin-mobile": "1rem",
        "space-xs": "0.25rem",
        "space-sm": "0.5rem",
        "space-md": "1rem",
        "space-lg": "1.5rem",
        "space-xl": "2.5rem",
      },
    },
  },
  plugins: [],
};

export default config;
