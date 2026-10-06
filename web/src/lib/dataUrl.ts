/** Extracts the raw Base64 payload from a `data:image/png;base64,...` URL.
 *  Returns null when the URL is not a PNG data URL, so callers can pass the
 *  result straight through to the Python bridge (which also accepts raw Base64).
 *
 *  Regression guard: the previous inline check compared
 *  `canvas.toDataURL("image/png").split(",", 1)[0]` (i.e. "data:image/png;base64")
 *  against "data:image/png", which was never equal, so sketches were silently
 *  never embedded in the exported PDF report.
 */
export function dataUrlToBase64(dataUrl: string): string | null {
  if (!dataUrl.startsWith("data:image/png")) {
    return null;
  }
  const comma = dataUrl.indexOf(",");
  if (comma === -1) {
    return null;
  }
  return dataUrl.slice(comma + 1);
}
