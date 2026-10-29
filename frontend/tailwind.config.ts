import type { Config } from "tailwindcss";

// Palette from "ClauseLens - Product Presentation Deck.pdf" (yellow, pink, turquoise,
// orange, indigo on off-white), presented in a softer, layered bento style:
// rounded cards, soft shadows, glowing accents and gentle motion.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#14121F",
        paper: "#F7F5FB",
        sun: { DEFAULT: "#FFDE59", deep: "#F5C800", soft: "#FFF5C7" },
        bubblegum: { DEFAULT: "#FF66C4", soft: "#FFE0F3" },
        lagoon: { DEFAULT: "#00C2CB", soft: "#D6F7F8" },
        tangerine: { DEFAULT: "#FF8A3D", soft: "#FFE7D6" },
        iris: { DEFAULT: "#6C5CE7", deep: "#5543D8", soft: "#ECE9FD" },
        slate: { DEFAULT: "#6E6A80", soft: "#EFEDF4" },
      },
      fontFamily: {
        display: ['"Archivo"', '"Arial Narrow"', "system-ui", "sans-serif"],
        body: ['"Bricolage Grotesque"', "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      borderRadius: { "4xl": "2rem", "5xl": "2.5rem" },
      boxShadow: {
        soft: "0 1px 2px rgba(20,18,31,0.04), 0 12px 32px -12px rgba(20,18,31,0.14)",
        lift: "0 2px 4px rgba(20,18,31,0.05), 0 28px 60px -20px rgba(20,18,31,0.28)",
        "glow-iris": "0 12px 40px -8px rgba(108,92,231,0.55)",
        "glow-sun": "0 12px 40px -8px rgba(245,200,0,0.6)",
        "glow-pink": "0 12px 40px -8px rgba(255,102,196,0.55)",
        "glow-lagoon": "0 12px 40px -8px rgba(0,194,203,0.5)",
        inset: "inset 0 0 0 1px rgba(20,18,31,0.06)",
      },
      keyframes: {
        float: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-10px)" } },
        "float-alt": {
          "0%,100%": { transform: "translateY(0) rotate(-3deg)" },
          "50%": { transform: "translateY(8px) rotate(3deg)" },
        },
        ring: {
          "0%": { transform: "scale(0.85)", opacity: "0.7" },
          "100%": { transform: "scale(1.9)", opacity: "0" },
        },
        marquee: { from: { transform: "translateX(0)" }, to: { transform: "translateX(-50%)" } },
        "pop-in": {
          "0%": { transform: "scale(0.85) translateY(8px)", opacity: "0" },
          "100%": { transform: "scale(1) translateY(0)", opacity: "1" },
        },
        "slide-up": {
          "0%": { transform: "translateY(24px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "grow-y": { from: { transform: "scaleY(0)" }, to: { transform: "scaleY(1)" } },
        shimmer: { from: { backgroundPosition: "-200% 0" }, to: { backgroundPosition: "200% 0" } },
        drift: {
          "0%,100%": { transform: "translate(0,0) scale(1)" },
          "33%": { transform: "translate(40px,-30px) scale(1.08)" },
          "66%": { transform: "translate(-30px,20px) scale(0.95)" },
        },
        wiggle: { "0%,100%": { transform: "rotate(-4deg)" }, "50%": { transform: "rotate(4deg)" } },
      },
      animation: {
        float: "float 5s ease-in-out infinite",
        "float-slow": "float 8s ease-in-out infinite",
        "float-alt": "float-alt 6s ease-in-out infinite",
        ring: "ring 2.4s cubic-bezier(0.2,0.6,0.4,1) infinite",
        marquee: "marquee 32s linear infinite",
        "pop-in": "pop-in 0.45s cubic-bezier(0.2,0.9,0.3,1.3) both",
        "slide-up": "slide-up 0.5s cubic-bezier(0.2,0.8,0.2,1) both",
        "fade-in": "fade-in 0.3s ease-out both",
        "grow-y": "grow-y 1s cubic-bezier(0.2,0.8,0.2,1) both",
        shimmer: "shimmer 2.2s linear infinite",
        drift: "drift 18s ease-in-out infinite",
        "drift-slow": "drift 26s ease-in-out infinite reverse",
        wiggle: "wiggle 3s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
