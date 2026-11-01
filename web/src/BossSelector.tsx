import { useId, useState } from 'react';
import { BOSSES } from '../scoring.mjs';

type Props = { value: string; onChange: (value: string) => void };

export function BossSelector({ value, onChange }: Props) {
  const [query, setQuery] = useState('');
  const id = useId();
  const normalized = query.trim().toLowerCase();
  const matches = Object.entries(BOSSES).filter(([, name]) =>
    name.toLowerCase().includes(normalized),
  );
  const selectionMatches = matches.some(([key]) => key === value);

  return (
    <div className="boss-picker">
      <label htmlFor={`${id}-search`}>Find your opponent</label>
      <div className="boss-search">
        <input
          id={`${id}-search`}
          type="search"
          autoComplete="off"
          placeholder="Search bosses, e.g. Isshin"
          value={query}
          onChange={event => setQuery(event.target.value)}
          aria-describedby={`${id}-hint`}
        />
        {query && <button type="button" onClick={() => setQuery('')}>Clear</button>}
      </div>
      <label htmlFor="boss" className="opponent-label">Your opponent</label>
      <select
        id="boss"
        name="boss"
        value={value}
        onChange={event => onChange(event.target.value)}
        aria-describedby={`${id}-hint`}
      >
        {!selectionMatches && (
          <optgroup label="Current selection">
            <option value={value}>{BOSSES[value]}</option>
          </optgroup>
        )}
        {matches.length > 0 && (
          <optgroup label={normalized ? 'Matching bosses' : 'All bosses'}>
            {matches.map(([key, name]) => <option key={key} value={key}>{name}</option>)}
          </optgroup>
        )}
      </select>
      <p id={`${id}-hint`} className="picker-hint" role="status">
        {matches.length === 0
          ? 'No matching bosses. Your current selection is kept.'
          : `${matches.length} ${matches.length === 1 ? 'boss matches' : 'bosses match'}. Choose a boss from the list.`}
      </p>
    </div>
  );
}