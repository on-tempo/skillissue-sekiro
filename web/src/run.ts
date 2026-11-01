import { BOSS_ALIASES, evaluate, type Run } from '../scoring.mjs';

export const EXAMPLE: Run = {
  boss: 'isshin', heals: 2, revives: 0,
  charmless: false, bell: false, prosthetic: false, art: false, cleared: true,
};
const flags = ['charmless', 'bell', 'prosthetic', 'art', 'cleared'] as const;

export function initialRecord(): { run: Run; shared: boolean; error: string } {
  if (!location.hash.includes('v=')) return { run: EXAMPLE, shared: false, error: '' };
  try {
    const params = new URLSearchParams(location.hash.slice(1));
    if (params.get('v') !== '1') throw Error();
    const boss = params.get('boss') ?? '';
    const run: Run = { ...EXAMPLE, boss: BOSS_ALIASES[boss] ?? boss };
    for (const field of ['heals', 'revives'] as const) {
      const value = params.get(field);
      if (value === null || value.trim() === '') throw Error();
      run[field] = Number(value);
    }
    for (const flag of flags) {
      const value = params.get(flag);
      if (value !== 'true' && value !== 'false') throw Error();
      run[flag] = value === 'true';
    }
    evaluate(run);
    return { run, shared: true, error: '' };
  } catch {
    return { run: EXAMPLE, shared: false, error: 'Invalid record link. Enter a new run.' };
  }
}

export function recordLink(run: Run): string {
  const url = new URL(location.href);
  url.hash = new URLSearchParams({
    v: '1', ...Object.fromEntries(Object.entries(run).map(([key, value]) => [key, String(value)])),
  }).toString();
  return url.href;
}

export function badges(run: Run): string[] {
  return [run.charmless ? 'Charmless' : 'Charm retained',
    run.bell ? 'Demon Bell active' : 'Demon Bell inactive'];
}

export function toolsLine(run: Run): string {
  return `Prosthetics: ${run.prosthetic ? 'used' : 'not used'} · Combat Arts: ${run.art ? 'used' : 'not used'}`;
}