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
 * Accessible instant tooltip badge (?) that works on both hover and touch/focus.
 * Uses data-tip + CSS ::before/::after so element.textContent stays clean.
 */
export function InfoTip({ text, title }: { text?: string; title?: string }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  return (
    <>
      <span
        className="info-tip"
        tabIndex={0}
        role="button"
        aria-label={text}
        data-tip={text}
        title="Tıklayarak tam açıklamayı okuyun / Click for details"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setOpen(true);
        }}
      />
      {open && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            e.stopPropagation();
            setOpen(false);
          }}
        >
          <div
            className="modal info-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="info-modal-header">
              <h3>{title || "Bilgi / Information"}</h3>
              <button
                type="button"
                className="info-modal-close"
                onClick={() => setOpen(false)}
                aria-label="Kapat"
              >
                ✕
              </button>
            </div>
            <div className="info-modal-body">
              {text.split("\n").map((line, idx) => {
                const trimmed = line.trim();
                if (!trimmed) return <div key={idx} className="info-modal-spacer" />;
                const colonIdx = trimmed.indexOf(":");
                if (colonIdx > 0 && colonIdx < 40) {
                  const label = trimmed.slice(0, colonIdx);
                  const val = trimmed.slice(colonIdx + 1).trim();
                  return (
                    <div key={idx} className="info-modal-row">
                      <strong className="info-modal-label">{label}:</strong>
                      <span className="info-modal-val">{val}</span>
                    </div>
                  );
                }
                return (
                  <div key={idx} className="info-modal-row">
                    <span>{trimmed}</span>
                  </div>
                );
              })}
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="primary"
                onClick={() => setOpen(false)}
              >
                Kapat / Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

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
  action?: ReactNode;
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
  action,
}: NumberFieldProps) {
  const invalid =
    value === null ||
    (value !== null && min !== undefined && value < min) ||
    (value !== null && max !== undefined && value > max);
  return (
    <div className="field" title={tooltip}>
      <div className="field-head">
        <span className="field-label">
          {label}
          <InfoTip text={tooltip} />
        </span>
        {action}
      </div>
      <input
        className={invalid ? "field-input invalid" : "field-input"}
        type="number"
        inputMode="decimal"
        aria-label={label}
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
    </div>
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
  action?: ReactNode;
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
  action,
}: SliderFieldProps) {
  const sliderLo = sliderMin ?? min;
  const sliderHi = sliderMax ?? max;
  const numeric = value ?? min;
  const sliderValue = Math.min(sliderHi, Math.max(sliderLo, numeric));
  return (
    <div className="field slider-field" title={tooltip}>
      <div className="slider-head">
        <span className="field-label">
          {label}
          <InfoTip text={tooltip} />
        </span>
        <div className="slider-head-controls">
          {action}
          <input
            className="field-input slider-number"
            type="number"
            inputMode="decimal"
            aria-label={label}
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

/**
 * Exposure duration field supporting both total seconds AND combined min + sec entry.
 */
export function DurationSliderField({
  label,
  value,
  onChange,
  tooltip,
  action,
  lang = "tr",
}: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  tooltip?: string;
  action?: ReactNode;
  lang?: string;
}) {
  const totalSec = Math.max(0, value ?? 0);
  const mins = Math.floor(totalSec / 60);
  const secs = Number((totalSec - mins * 60).toFixed(1));
  const sliderVal = Math.min(1800, Math.max(5, totalSec));
  const tr = lang === "tr";

  return (
    <div className="field slider-field" title={tooltip}>
      <div className="slider-head">
        <span className="field-label">
          {label}
          <InfoTip text={tooltip} />
        </span>
        <div className="slider-head-controls">
          {action}
          <input
            className="field-input slider-number"
            type="number"
            inputMode="decimal"
            aria-label={label}
            value={value === null || Number.isNaN(value) ? "" : Number(value.toFixed(1))}
            min={0.1}
            max={100000}
            step={1}
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
      </div>
      <div className="duration-split-row">
        <div className="duration-unit-box">
          <input
            className="field-input duration-input"
            type="number"
            min={0}
            max={1600}
            step={1}
            value={mins}
            aria-label={tr ? "Dakika" : "Minutes"}
            onChange={(event) => {
              const newMins = Math.max(0, Math.floor(Number(event.target.value) || 0));
              onChange(Math.max(0.1, newMins * 60 + secs));
            }}
          />
          <span className="duration-unit-label">{tr ? "dk" : "min"}</span>
        </div>
        <div className="duration-unit-box">
          <input
            className="field-input duration-input"
            type="number"
            min={0}
            max={59.9}
            step={1}
            value={secs}
            aria-label={tr ? "Saniye" : "Seconds"}
            onChange={(event) => {
              const newSecs = Math.max(0, Number(event.target.value) || 0);
              onChange(Math.max(0.1, mins * 60 + newSecs));
            }}
          />
          <span className="duration-unit-label">{tr ? "sn" : "sec"}</span>
        </div>
        <input
          className="slider"
          type="range"
          min={5}
          max={1800}
          step={5}
          value={sliderVal}
          onChange={(event) => onChange(Number(event.target.value))}
        />
      </div>
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
  action?: ReactNode;
}

export function SelectField({
  label,
  value,
  options,
  onChange,
  tooltip,
  disabled,
  action,
}: SelectFieldProps) {
  return (
    <div className="field" title={tooltip}>
      <div className="field-head">
        <span className="field-label">
          {label}
          <InfoTip text={tooltip} />
        </span>
        {action}
      </div>
      <select
        className="field-input"
        aria-label={label}
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
    </div>
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
      <span className="field-label">
        {label}
        <InfoTip text={tooltip} />
      </span>
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
      <span>
        {label}
        <InfoTip text={tooltip} />
      </span>
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
  headerAction?: ReactNode;
}

export function Group({
  title,
  children,
  className,
  id,
  collapsible = true,
  open = true,
  headerAction,
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
      <summary className="group-title">
        <span>{title}</span>
        {headerAction && (
          <span
            className="group-header-action"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
            }}
          >
            {headerAction}
          </span>
        )}
      </summary>
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
      <span className="output-label">
        {label}
        <InfoTip text={tooltip} />
      </span>
      <span className="output-value">{value}</span>
    </div>
  );
}
