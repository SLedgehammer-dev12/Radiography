import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";

export const UnitContext = createContext<{ inch: boolean }>({ inch: false });

/**
 * Always-visible, draggable vertical scrollbar for the document.
 * Independent of the OS overlay-scrollbar setting (macOS "when scrolling").
 */
export function PageScrollbar() {
  const [thumb, setThumb] = useState({ top: 4, height: 80 });
  const [dragging, setDragging] = useState(false);
  const thumbHeight = useRef(80);

  useEffect(() => {
    const update = () => {
      const doc = document.documentElement;
      const viewport = doc.clientHeight;
      const total = doc.scrollHeight;
      const height = Math.max(48, Math.round(viewport * (viewport / total)));
      thumbHeight.current = height;
      const maxTop = Math.max(0, viewport - 8 - height);
      const progress = total > viewport ? window.scrollY / (total - viewport) : 0;
      setThumb({ top: 4 + progress * maxTop, height });
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    const observer = new ResizeObserver(update);
    observer.observe(document.documentElement);
    observer.observe(document.body);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
      observer.disconnect();
    };
  }, []);

  const startDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    const doc = document.documentElement;
    const viewport = doc.clientHeight;
    const total = doc.scrollHeight;
    if (total <= viewport) return;
    event.preventDefault();
    const startY = event.clientY;
    const startScroll = window.scrollY;
    const maxTop = Math.max(1, viewport - 8 - thumbHeight.current);
    const ratio = (total - viewport) / maxTop;
    setDragging(true);
    const move = (moveEvent: PointerEvent) => {
      window.scrollTo({ top: startScroll + (moveEvent.clientY - startY) * ratio });
    };
    const up = () => {
      setDragging(false);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const jumpTo = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget) return;
    const doc = document.documentElement;
    const viewport = doc.clientHeight;
    const total = doc.scrollHeight;
    if (total <= viewport) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const progress = Math.min(
      1,
      Math.max(0, (event.clientY - rect.top) / rect.height),
    );
    window.scrollTo({ top: progress * (total - viewport), behavior: "smooth" });
  };

  return (
    <div className="page-scrollbar" aria-hidden="true" onPointerDown={jumpTo}>
      <div
        className={dragging ? "page-scrollbar-thumb dragging" : "page-scrollbar-thumb"}
        style={{ top: thumb.top, height: thumb.height }}
        onPointerDown={startDrag}
      />
    </div>
  );
}

interface NumberFieldProps {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  min?: number;
  max?: number;
  step?: number;
  tooltip?: string;
  placeholder?: string;
  disabled?: boolean;
}

export function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step = 0.01,
  tooltip,
  placeholder,
  disabled,
}: NumberFieldProps) {
  const invalid =
    value === null ||
    (value !== null && min !== undefined && value < min) ||
    (value !== null && max !== undefined && value > max);
  return (
    <label className="field" title={tooltip}>
      <span className="field-label">{label}</span>
      <input
        className={invalid ? "field-input invalid" : "field-input"}
        type="number"
        inputMode="decimal"
        value={value === null || Number.isNaN(value) ? "" : value}
        min={min}
        max={max}
        step={step}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(event) => {
          const raw = event.target.value;
          if (raw === "") {
            onChange(null);
            return;
          }
          const parsed = Number(raw.replace(",", "."));
          onChange(Number.isFinite(parsed) ? parsed : null);
        }}
      />
    </label>
  );
}

/** NumberField that displays/accepts inches when the unit mode is active. */
export function LengthField(props: NumberFieldProps) {
  const { inch } = useContext(UnitContext);
  const factor = inch ? 1 / 25.4 : 1;
  const display =
    props.value === null || Number.isNaN(props.value)
      ? null
      : Number((props.value * factor).toFixed(4));
  return (
    <NumberField
      {...props}
      value={display}
      step={inch ? 0.01 : props.step}
      onChange={(value) =>
        props.onChange(value === null ? null : value / factor)
      }
    />
  );
}

interface SliderFieldProps {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  min: number;
  max: number;
  step?: number;
  sliderMin?: number;
  sliderMax?: number;
  tooltip?: string;
  disabled?: boolean;
}

/** Numeric field with a synchronized range slider (mobile-style control). */
export function SliderField({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  sliderMin,
  sliderMax,
  tooltip,
  disabled,
}: SliderFieldProps) {
  const sliderLo = sliderMin ?? min;
  const sliderHi = sliderMax ?? max;
  const numeric = value ?? min;
  const sliderValue = Math.min(sliderHi, Math.max(sliderLo, numeric));
  return (
    <div className="field slider-field" title={tooltip}>
      <div className="slider-head">
        <span className="field-label">{label}</span>
        <input
          className="field-input slider-number"
          type="number"
          inputMode="decimal"
          value={value === null || Number.isNaN(value) ? "" : value}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          onChange={(event) => {
            const raw = event.target.value;
            if (raw === "") {
              onChange(null);
              return;
            }
            const parsed = Number(raw.replace(",", "."));
            onChange(Number.isFinite(parsed) ? parsed : null);
          }}
        />
      </div>
      <input
        className="slider"
        type="range"
        min={sliderLo}
        max={sliderHi}
        step={step}
        value={sliderValue}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </div>
  );
}

/** Unit-aware slider for millimetre fields (inch mode supported). */
export function LengthSliderField(props: SliderFieldProps) {
  const { inch } = useContext(UnitContext);
  const factor = inch ? 1 / 25.4 : 1;
  const display =
    props.value === null || Number.isNaN(props.value)
      ? null
      : Number((props.value * factor).toFixed(4));
  return (
    <SliderField
      {...props}
      value={display}
      min={props.min}
      max={props.max}
      sliderMin={
        props.sliderMin === undefined
          ? undefined
          : Number((props.sliderMin * factor).toFixed(4))
      }
      sliderMax={
        props.sliderMax === undefined
          ? undefined
          : Number((props.sliderMax * factor).toFixed(4))
      }
      onChange={(value) =>
        props.onChange(value === null ? null : value / factor)
      }
    />
  );
}

interface SelectOption {
  value: string;
  label: string;
}

interface SelectFieldProps {
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  tooltip?: string;
  disabled?: boolean;
}

export function SelectField({
  label,
  value,
  options,
  onChange,
  tooltip,
  disabled,
}: SelectFieldProps) {
  return (
    <label className="field" title={tooltip}>
      <span className="field-label">{label}</span>
      <select
        className="field-input"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

interface RadioGroupProps {
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  tooltip?: string;
}

export function RadioGroup({
  label,
  value,
  options,
  onChange,
  tooltip,
}: RadioGroupProps) {
  return (
    <div className="field" title={tooltip}>
      <span className="field-label">{label}</span>
      <div className="radio-row">
        {options.map((option) => (
          <label key={option.value} className="radio-option">
            <input
              type="radio"
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

interface CheckFieldProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  tooltip?: string;
}

export function CheckField({ label, checked, onChange, tooltip }: CheckFieldProps) {
  return (
    <label className="field field-inline" title={tooltip}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}

interface GroupProps {
  title: string;
  children: ReactNode;
  className?: string;
  id?: string;
  collapsible?: boolean;
  open?: boolean;
}

export function Group({
  title,
  children,
  className,
  id,
  collapsible = true,
  open = true,
}: GroupProps) {
  const classes = className ? `group ${className}` : "group";
  if (!collapsible) {
    return (
      <section id={id} className={classes}>
        <h3 className="group-title">{title}</h3>
        <div className="group-body">{children}</div>
      </section>
    );
  }
  return (
    <details id={id} className={classes} open={open}>
      <summary className="group-title">{title}</summary>
      <div className="group-body">{children}</div>
    </details>
  );
}

interface OutputRowProps {
  label: string;
  value: string;
  tooltip?: string;
  testId?: string;
}

export function OutputRow({ label, value, tooltip, testId }: OutputRowProps) {
  return (
    <div className="output-row" title={tooltip} data-testid={testId}>
      <span className="output-label">{label}</span>
      <span className="output-value">{value}</span>
    </div>
  );
}
