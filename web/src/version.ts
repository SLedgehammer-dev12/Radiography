declare const __APP_VERSION__: string | undefined;

export const FALLBACK_VERSION =
  typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "2.0.4";
