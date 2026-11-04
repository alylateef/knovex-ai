import React from 'react';

interface Option<T> {
  value: T;
  label: string;
}

interface SegmentedControlProps<T extends string | number> {
  name: string;
  label: string;
  value: T;
  onChange: (value: T) => void;
  options: Option<T>[];
}

export function SegmentedControl<T extends string | number>({
  name,
  label,
  value,
  onChange,
  options,
}: SegmentedControlProps<T>): React.ReactElement {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex border border-line bg-elevated/40 p-0.5 rounded-input"
    >
      {options.map((opt) => {
        const checked = opt.value === value;
        return (
          <button
            key={String(opt.value)}
            type="button"
            role="radio"
            aria-checked={checked}
            name={name}
            onClick={() => onChange(opt.value)}
            className={`px-2.5 py-1 text-xs font-mono rounded-input transition-all ${
              checked
                ? 'bg-surface text-ink font-medium shadow-sm border border-line'
                : 'text-secondary hover:text-ink border border-transparent'
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
