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
