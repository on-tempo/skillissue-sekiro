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
  const [rank, setRank] = useState('Reveal your record to compare with the community.');
  const [pending, setPending] = useState(false);
  const [shareStatus, setShareStatus] = useState('');
  const [fallbackLink, setFallbackLink] = useState('');
  const [saving, setSaving] = useState(false);
  const [canContribute, setCanContribute] = useState(false);
  const [contribution, setContribution] = useState('');
  const [contributing, setContributing] = useState(false);
  const currentKey = useRef('');
  const busy = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const result = evaluate(record);
  useEffect(() => () => controller.current?.abort(), []);

  function update(patch: Partial<Draft>) {
    setDraft(previous => ({ ...previous, ...patch }));
    setLabel('CHANGES PENDING · REVEAL AGAIN');
    setError('');
    setCanContribute(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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
    currentKey.current = key;
    setCanContribute(true);
    setContribution('');
    controller.current?.abort();
    const requestController = new AbortController();
    controller.current = requestController;
    setPending(true);
    setRank('Checking your rank…');
    const timeout = window.setTimeout(() => requestController.abort(), 15000);
    try {
      const params = new URLSearchParams({ boss: run.boss, score: String(evaluate(run).score),
        charmless: String(run.charmless), bell: String(run.bell) });
      const response = await fetch(`/api/percentile?${params}`, {
        credentials: 'same-origin', signal: requestController.signal,
      });
      if (!response.ok) throw Error('Community rankings are temporarily unavailable.');
      const text = rankingText({ percentile: await response.json() });
      if (controller.current === requestController) setRank(text);
    } catch {
      if (controller.current === requestController) {
        setRank('Ranking unavailable. Your score is ready; Reveal again to retry.');
      }
    } finally {
      clearTimeout(timeout);
      if (controller.current === requestController) setPending(false);
    }
  }

  async function contribute() {
    if (busy.current || !canContribute) return;
    busy.current = true;
    setContributing(true);
    const run = record;
    const key = JSON.stringify(run);
    // This POST owns the newest ranking for this record.
    controller.current?.abort();
    controller.current = null;
    setPending(false);
    const postController = new AbortController();
    const timeout = window.setTimeout(() => postController.abort(), 15000);
    try {
      const response = await fetch('/api/submit', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: key,
        signal: postController.signal,
      });
      if (response.status === 429) throw Error('Contribution limit reached. Keep calculating freely; save again later.');
      if (!response.ok) throw Error('Could not save. Your score and card are still available.');
      const data = await response.json();
      const text = rankingText(data);
      if (currentKey.current === key) {
        setRank(text);
        setCanContribute(false);
        setContribution(data.submission === 'duplicate'
          ? 'Already contributed within 24 hours. Not counted again.'
          : 'Record contributed. Thank you!');
      }
    } catch (cause) {
      if (currentKey.current === key) setContribution(
        cause instanceof Error && cause.name !== 'AbortError' ? cause.message
          : 'Save timed out. Retry safely; identical records are counted once.');
    } finally {
      clearTimeout(timeout);
      busy.current = false;
      setContributing(false);
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
          <fieldset style={{ border: 0, margin: 0, padding: 0, minWidth: 0 }}>
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
            <button type="submit" className="primary" >Reveal my record <span>→</span></button>
          </fieldset>
          <p id="error" role="alert">{error}</p>
          <p className="fine">Calculate as often as you like. Reveal only looks up rankings; use Contribute to add this clear to community statistics.</p>
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
        <div className="contribution-panel">
          <button type="button" className="primary" onClick={contribute} disabled={!canContribute || contributing || pending}>
            {contributing ? 'Contributing…' : 'Contribute this clear'}
          </button>
          <p className="fine">Only contribute a real completed rematch. Up to 60 new records per browser per hour by default; exact repeats count once within 24 hours.</p>
          <p role="status">{contribution}</p>
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