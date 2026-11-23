// Looks images up by file name in src/assets/figma/. Missing files simply return null
// (the UI shows a fallback), so the app runs before the artwork is downloaded.
const files = import.meta.glob("./figma/*.{png,svg}", { eager: true, query: "?url", import: "default" });

/** asset("icon-plumber") -> "/src/assets/figma/icon-plumber.png" or null */
export function asset(name) {
  return files[`./figma/${name}.png`] ?? files[`./figma/${name}.svg`] ?? null;
}
