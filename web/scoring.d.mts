export interface Run {
  boss: string;
  heals: number;
  revives: number;
  charmless: boolean;
  bell: boolean;
  prosthetic: boolean;
  art: boolean;
  cleared: boolean;
}
export interface Result {
  score: number;
  grade: 'S' | 'A' | 'B' | 'C';
  title: string;
  boss: string;
}
export const BOSSES: Record<string, string>;
export const BOSS_ALIASES: Record<string, string>;
export function evaluate(run: Run): Result;