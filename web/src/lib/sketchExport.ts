import { dataUrlToBase64 } from "./dataUrl";

/** Rasterises an inline SVG (by container id) to a PNG base64 string. */
export async function svgToPngBase64(containerId: string): Promise<string | null> {
  const container = document.getElementById(containerId);
  const svg = container?.querySelector("svg");
  if (!svg) return null;
  const clone = svg.cloneNode(true) as SVGSVGElement;
  const styles = getComputedStyle(document.documentElement);
  const resolve = (value: string | null) => {
    if (!value || !value.includes("var(")) return value;
    return value.replace(/var\((--[^)]+)\)/g, (_, name: string) => {
      const resolved = styles.getPropertyValue(name).trim();
      return resolved || "#000000";
    });
  };
  clone.querySelectorAll("*").forEach((element) => {
    for (const attribute of ["fill", "stroke"]) {
      const value = resolve(element.getAttribute(attribute));
      if (value) element.setAttribute(attribute, value);
    }
  });
  clone.setAttribute("width", "900");
  clone.setAttribute("height", "900");
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const serialized = new XMLSerializer().serializeToString(clone);
  const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(serialized)}`;
  const image = new Image();
  await new Promise<void>((resolvePromise, rejectPromise) => {
    image.onload = () => resolvePromise();
    image.onerror = () => rejectPromise(new Error("SVG rasterisation failed"));
    image.src = url;
  });
  const canvas = document.createElement("canvas");
  canvas.width = 900;
  canvas.height = 900;
  const context = canvas.getContext("2d");
  if (!context) return null;
  context.fillStyle =
    styles.getPropertyValue("--bg-alt").trim() || "#ffffff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return dataUrlToBase64(canvas.toDataURL("image/png"));
}

export function downloadBase64(base64: string, filename: string) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const blob = new Blob([bytes], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
