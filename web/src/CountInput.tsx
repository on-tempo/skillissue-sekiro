import { useId } from 'react';

type Props = {
  name: string;
  label: string;
  hint: string;
  value: string;
  max: number;
  onChange: (value: string) => void;
};

export function CountInput({ name, label, hint, value, max, onChange }: Props) {
  const id = useId();
  const number = Number(value);
  const base = Number.isFinite(number) ? Math.min(max, Math.max(0, Math.trunc(number))) : 0;

  function step(direction: number) {
    onChange(String(Math.min(max, Math.max(0, base + direction))));
  }

  return (
    <div className="count-field">
      <label htmlFor={id}>{label}</label>
      <div className="count-control">
        <button type="button" aria-label={`Decrease ${label.toLowerCase()}`} disabled={base <= 0} onClick={() => step(-1)}>−</button>
        <input
          id={id}
          name={name}
          type="number"
          inputMode="numeric"
          min="0"
          max={max}
          step="1"
          required
          value={value}
          onChange={event => onChange(event.target.value)}
          aria-describedby={`${id}-hint`}
        />
        <button type="button" aria-label={`Increase ${label.toLowerCase()}`} disabled={base >= max} onClick={() => step(1)}>+</button>
      </div>
      <small id={`${id}-hint`}>{hint}</small>
    </div>
  );
}