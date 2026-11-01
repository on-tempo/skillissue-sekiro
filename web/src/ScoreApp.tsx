import { useEffect, useRef, useState, type FormEvent } from 'react';
import { evaluate, type Run } from '../scoring.mjs';
import { initialRecord, recordLink } from './run';
import { downloadCard } from './downloadCard';
import { ResultCard } from './ResultCard';
import { BossSelector } from './BossSelector';
import { CountInput } from './CountInput';
import './inputs.css';

type Draft = Omit<Run, 'heals' | 'revives'> & { heals: string; revives: string };
const draftOf = (run: Run): Draft => ({ ...run, heals: String(run.heals), revives: String(run.revives) });

function rankingText(data: unknown): string {
  const response = data as { percentile?: { status?: string; n?: number; min_n?: number; top_percent?: number } };
  const p = response?.percentile;
  if (!p || !Number.isInteger(p.n) || p.n! < 0) throw Error('Invalid ranking response.');
  if (p.status === 'ok' && typeof p.top_percent === 'number' && p.top_percent >= 1 && p.top_percent <= 100) {
    return `Top ${p.top_percent}% of ${p.n} submitted records for this boss and challenge setting · self-reported`;
  }
  if (p.status === 'collecting' && Number.isInteger(p.min_n) && p.min_n! > 0) {
    return `Rankings unlock at ${p.min_n} records for this boss and setting (${p.n} so far).`;
  }
  throw Error('Invalid ranking response.');
}

export function ScoreApp() {
  const [initial] = useState(initialRecord);
  const [draft, setDraft] = useState(() => draftOf(initial.run));
  const [record, setRecord] = useState(initial.run);
  const [label, setLabel] = useState(initial.shared ? 'SHARED RECORD · UNVERIFIED' : 'EXAMPLE RECORD');
  const [error, setError] = useState(initial.error);
  const [rank, setRank] = useState('');
  const [pending, setPending] = useState(false);
  const [shareStatus, setShareStatus] = useState('');
  const [fallbackLink, setFallbackLink] = useState('');
  const [saving, setSaving] = useState(false);
  const cache = useRef(new Map<string, string>());
  const busy = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const result = evaluate(record);
  useEffect(() => () => controller.current?.abort(), []);

  function update(patch: Partial<Draft>) {
    setDraft(previous => ({ ...previous, ...patch }));
    setLabel('CHANGES PENDING · REVEAL AGAIN');
    setError('');
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    let run: Run;
    try {
      if (!draft.heals.trim() || !draft.revives.trim()) throw Error('Enter both counts.');
      run = { ...draft, heals: Number(draft.heals), revives: Number(draft.revives) };
      evaluate(run);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Check your inputs.');
      return;
    }
    setRecord(run);
    setLabel('YOUR VICTORY RECORD');
    setError('');
    setShareStatus('');
    setFallbackLink('');
    const key = JSON.stringify(run);
    const cached = cache.current.get(key);
    if (cached !== undefined) { setRank(cached); return; }
    busy.current = true;
    setPending(true);
    setRank('Checking your rank…');
    controller.current = new AbortController();
    const timeout = window.setTimeout(() => controller.current?.abort(), 15000);
    try {
      const response = await fetch('/api/submit', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: key, signal: controller.current.signal,
      });
      if (response.status === 429) throw Error('Too many submissions. Wait before trying again.');
      if (!response.ok) throw Error('Could not submit this record. Your local card is still available.');
      const text = rankingText(await response.json());
      cache.current.set(key, text);
      setRank(text);
    } catch (cause) {
      setRank('Community rankings are temporarily unavailable.');
      setError(cause instanceof Error && cause.name !== 'AbortError'
        ? cause.message : 'The request timed out or was cancelled. You can try Reveal again.');
    } finally {
      clearTimeout(timeout);
      busy.current = false;
      setPending(false);
    }
  }

  async function share() {
    const link = recordLink(record);
    try {
      await navigator.clipboard.writeText(link);
      setFallbackLink('');
      setShareStatus('Record link copied.');
    } catch {
      setFallbackLink(link);
      setShareStatus('Copy the link below.');
    }
  }

  async function save() {
    if (saving) return;
    setSaving(true);
    try {
      await downloadCard(record, result, rank);
      setShareStatus('Your card image is ready. Check your downloads.');
    } catch {
      setShareStatus('Could not create the image. Try copying the record link.');
    } finally { setSaving(false); }
  }

  return (
    <section id="challenge" className="workspace">
      <div className="input-panel">
        <div className="section-label"><span>01 — THE RUN</span><span>BOSS REMATCHES ONLY</span></div>
        <h2>How did you prevail?</h2>
        <p className="muted">Tell the story of one successful boss rematch.</p>
        <form id="run-form" onSubmit={submit} aria-busy={pending}>
          <fieldset disabled={pending} style={{ border: 0, margin: 0, padding: 0, minWidth: 0 }}>
            <BossSelector value={draft.boss} onChange={boss => update({ boss })} />
            <div className="field-title">Challenge conditions <span>Recorded as separate badges</span></div>
            <label className="toggle-row">
              <div><strong>Charmless</strong><small>You returned Kuro’s Charm</small></div>
              <input type="checkbox" name="charmless" checked={draft.charmless} onChange={e => update({ charmless: e.target.checked })} />
              <span className="switch" />
            </label>
            <label className="toggle-row">
              <div><strong>Demon Bell</strong><small>The bell’s burden was active</small></div>
              <input type="checkbox" name="bell" checked={draft.bell} onChange={e => update({ bell: e.target.checked })} />
              <span className="switch" />
            </label>
            <div className="number-grid">
              <CountInput
                name="heals"
                label="Healing uses"
                hint="All healing uses, including Gourds and Pellets"
                value={draft.heals}
                max={999}
                onChange={heals => update({ heals })}
              />
              <CountInput
                name="revives"
                label="Resurrections"
                hint="Times you rose during this fight"
                value={draft.revives}
                max={99}
                onChange={revives => update({ revives })}
              />
            </div>
            <div className="field-title">Tools of the trade <span>Shown on your card; no penalty</span></div>
            <div className="check-grid">
              <label><input type="checkbox" name="prosthetic" checked={draft.prosthetic} onChange={e => update({ prosthetic: e.target.checked })} /> Prosthetic tools</label>
              <label><input type="checkbox" name="art" checked={draft.art} onChange={e => update({ art: e.target.checked })} /> Combat Arts</label>
            </div>
            <label className="confirm"><input type="checkbox" name="cleared" required checked={draft.cleared} onChange={e => update({ cleared: e.target.checked })} /> I defeated this boss in Reflection of Strength.</label>
            <button type="submit" className="primary" disabled={pending}>{pending ? 'Submitting…' : 'Reveal my record'} <span>→</span></button>
          </fieldset>
          <p id="error" role="alert">{error}</p>
          <p className="fine">Self-reported, unverified · Submitted records are stored with a pseudonymous key to calculate rankings · No game account connection</p>
        </form>
      </div>
      <div className="output-panel">
        <div className="section-label"><span>02 — THE PROOF</span><span>{label}</span></div>
        <ResultCard run={record} result={result} rank={rank} />
        <div className="explanation">
          <h3>Behind your grade</h3>
          <p>100 base points − {record.heals} healing uses × 5 − {record.revives} resurrections × 15 = {result.score} points{result.score === 0 ? ' (minimum 0)' : ''}. Grade {result.grade}.</p>
          <p className="muted">Charmless and Demon Bell are separate challenge badges. Zero healing does not mean a no-hit run.</p>
        </div>
        <div className="share-actions">
          <button type="button" onClick={save} disabled={saving}>{saving ? 'Creating image…' : '↓ Download card'}</button>
          <button type="button" onClick={share}>↗ Copy record link</button>
        </div>
        <p role="status" className="fine">{shareStatus}</p>
        {fallbackLink && <input aria-label="Record link" readOnly value={fallbackLink} onFocus={e => e.target.select()} style={{ width: '100%' }} />}
      </div>
    </section>
  );
}