import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadSerif } from "@remotion/google-fonts/SourceSerif4";

// Tokens de web/src/index.css (tema claro, crema).
export const C = {
  bg: "rgb(241,232,214)",
  surface: "rgb(233,222,200)",
  surface2: "rgb(225,212,187)",
  outline: "rgb(207,191,162)",
  text: "rgb(42,36,28)",
  text2: "rgb(86,76,63)",
  accent: "rgb(27,70,160)",
  onAccent: "rgb(255,255,255)",
  accentContainer: "rgb(214,221,240)",
  onAccentContainer: "rgb(10,34,82)",
  success: "rgb(19,97,42)",
  highlight: "rgb(241,220,147)",
  shadow: "0 1px 3px rgba(60,45,20,0.08), 0 4px 12px rgba(60,45,20,0.06)",
  shadowBig: "0 2px 6px rgba(60,45,20,0.10), 0 18px 48px rgba(60,45,20,0.12)",
};

export const sans = loadInter("normal", { weights: ["400", "500"], subsets: ["latin"] }).fontFamily;
export const serif = loadSerif("normal", { weights: ["400", "600"], subsets: ["latin"] }).fontFamily;

export const FPS = 30;
