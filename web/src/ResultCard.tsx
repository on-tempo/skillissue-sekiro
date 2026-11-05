import type { Run, Result } from '../scoring.mjs';
import mark from '../moon-katana-mark.svg';
import { badges, toolsLine } from './run';

export function ResultCard({ run, result, rank }: {
  run: Run; result: Result; rank: string;
}) {
  const top = rank.match(/^Top (\d+)%/);
  const collecting = rank.match(/Rankings unlock at (\d+) records.*\((\d+) so far\)/);
  return (
    <article id="result" aria-live="polite">
      <div className="card-top">
        <span>SEKIRO / REFLECTION OF STRENGTH</span>
        <img className="seal" src={mark} alt="Katana and full moon" />
      </div>
      <p className="card-kicker">A VICTORY EARNED</p>
      <h2 id="result-boss">{result.boss}</h2>
      <div className="grade-line">
        <span id="grade">{result.grade}</span>
        <div><strong>{result.title}</strong><p>Performance grade · Prototype rules v0.1</p></div>
      </div>
      <div className="badges">{badges(run).map(text => <span key={text}>{text}</span>)}</div>
      <div className="metrics">
        <div><span>Healing</span><strong>{run.heals}<small>uses</small></strong></div>
        <div><span>Resurrections</span><strong>{run.revives}<small>times</small></strong></div>
        <div><span>Score</span><strong>{result.score}<small>/100</small></strong></div>
      </div>
      <p className="tools">{toolsLine(run)} · Boss rematch</p>
      <div className="community-ranking" role="status">
        <span className="ranking-label">COMMUNITY COMPARISON</span>
        <strong>{top ? `Top ${top[1]}%` : collecting ? `${collecting[2]} / ${collecting[1]} records` : 'Your community rank'}</strong>
        <p>{rank}</p>
        <small>Same boss · {run.charmless ? 'Charmless' : 'With charm'} · {run.bell ? 'Demon Bell' : 'No bell'}<br />Record ranking, not a verified player ranking.</small>
      </div>
      <div className="card-bottom"><span>skillissue.gg</span><span>SELF-REPORTED · UNVERIFIED</span></div>
    </article>
  );
}