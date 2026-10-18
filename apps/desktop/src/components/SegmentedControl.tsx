import type { CSSProperties } from "react";
interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  description?: string;
}

interface SegmentedControlProps<T extends string> {
  label: string;
  value: T;
  options: SegmentedOption<T>[];
  onChange: (value: T) => void;
}

export function SegmentedControl<T extends string>({
  label,
  value,
  options,
  onChange
}: SegmentedControlProps<T>) {
  return (
    <fieldset className="segmented-field">
      <legend>{label}</legend>
      <div className="segmented-control" role="group" aria-label={label}
        style={{"--segment-count":options.length,"--segment-index":Math.max(0,options.findIndex(option=>option.value===value))} as CSSProperties}>
        <span className="segment-indicator" aria-hidden="true" />
        {options.map((option) => (
          <button
            type="button"
            key={option.value}
            className={option.value === value ? "segment is-active" : "segment"}
            aria-pressed={option.value === value}
            onClick={() => onChange(option.value)}
          >
            <span>{option.label}</span>
            {option.description ? <small>{option.description}</small> : null}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
