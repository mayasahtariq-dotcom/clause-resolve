import type { Config } from "tailwindcss";

// Design tokens sampled from "ClauseLens - Product Presentation Deck.pdf":
// yellow signature canvas, bold black outlines with hard offset shadows,
// pink / turquoise / orange / indigo accent panels on an off-white page.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0A0A0A",
        paper: "#FBF9F4",
        sun: { DEFAULT: "#FFDE59", deep: "#F5C800", soft: "#FFF3BF" },
        bubblegum: { DEFAULT: "#FF66C4", soft: "#FFD6EE" },
        lagoon: { DEFAULT: "#00C2CB", soft: "#D5F6F7" },
        tangerine: { DEFAULT: "#FF8A3D", soft: "#FFE3CF" },
        iris: { DEFAULT: "#5B5BD6", soft: "#E3E3FA" },
        slate: { DEFAULT: "#6B6B6B", soft: "#EDEDED" },
      },
      fontFamily: {
        display: ['"Archivo"', '"Arial Narrow"', "system-ui", "sans-serif"],
        body: ['"Bricolage Grotesque"', "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      borderWidth: { 3: "3px", 4: "4px" },
      boxShadow: {
        brut: "6px 6px 0 0 #0A0A0A",
        "brut-sm": "3px 3px 0 0 #0A0A0A",
        "brut-lg": "10px 10px 0 0 #0A0A0A",
      },
      borderRadius: { brut: "4px" },
      fontStretch: { condensed: "87.5%" },
    },
  },
  plugins: [],
} satisfies Config;
