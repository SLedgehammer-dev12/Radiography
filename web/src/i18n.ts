import type { ExposuresProvenance } from "./types";

export type Translator = (key: string, ...args: unknown[]) => string;

function format(template: string, args: unknown[]): string {
  let sequential = 0;
  return template.replace(/\{([^}]*)\}/g, (match, spec: string) => {
    const [name, fmt] = spec.split(":");
    let value: unknown;
    if (name === "") {
      value = args[sequential++];
    } else if (/^\d+$/.test(name)) {
      value = args[Number(name)];
    } else {
      value = undefined;
    }
    if (value === undefined) return match;
    if (fmt && typeof value === "number") {
      const fixed = fmt.match(/^\.(\d+)f$/);
      if (fixed) return value.toFixed(Number(fixed[1]));
      if (/^\d+d$/.test(fmt)) return String(Math.round(value));
    }
    return String(value);
  });
}

export function makeTranslator(
  strings: Record<string, string>,
  fallback: Record<string, string> = {},
): Translator {
  return (key: string, ...args: unknown[]) => {
    const template = strings[key] ?? fallback[key] ?? key;
    return format(template, args);
  };
}

export function formatExposuresProvenance(
  prov: ExposuresProvenance | undefined,
  t: Translator,
): string {
  if (!prov) return "";
  if (prov.method === "annex_a") {
    let text = t(
      "exp_prov_annex_a",
      prov.figure,
      prov.t_over_de,
      prov.ratio_name,
      prov.ratio,
      prov.n,
    );
    if (
      prov.next_n != null &&
      prov.next_ratio != null &&
      prov.next_distance_mm != null
    ) {
      text += ` — ${t(
        prov.next_op === "ge" ? "exp_prov_next_ge" : "exp_prov_next_le",
        prov.next_n,
        prov.ratio_name,
        prov.next_ratio,
        prov.next_distance_mm,
      )}`;
    }
    if (prov.l3_dw) text += ` — ${t("exp_prov_l3")}`;
    return text;
  }
  if (prov.method === "panoramic") return t("exp_prov_panoramic");
  if (prov.method === "dwdi_rule") {
    let text = t("exp_prov_dwdi", prov.ratio, prov.n);
    if (prov.dwdi_coverage && prov.dwdi_coverage.available_across > 0) {
      const cov = prov.dwdi_coverage;
      const isTr = t("language") === "tr" || !t("language");
      const tag = cov.is_sufficient
        ? (isTr ? "Kurtarıyor ✓" : "Sufficient ✓")
        : (isTr ? `Kurtarmıyor ⚠ (Min. ${cov.w_min_req.toFixed(1)} mm)` : `Insufficient ⚠ (Min. ${cov.w_min_req.toFixed(1)} mm)`);
      const label = isTr ? "Kapsama" : "Coverage";
      const enteredLabel = isTr ? "Girilen" : "Entered";
      text += ` | ${label}: Min. ${cov.w_min_req.toFixed(1)} mm / ${enteredLabel}: ${cov.available_across.toFixed(0)} mm (${tag})`;
    }
    return text;
  }
  if (prov.method === "out_of_chart") {
    return t("exp_prov_out_of_chart", prov.n);
  }
  return t("exp_prov_fallback", prov.n);
}
