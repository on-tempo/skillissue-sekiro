export const BOSSES = {
  gyoubu: 'Gyoubu Oniwa',
  butterfly: 'Lady Butterfly',
  genichiro: 'Genichiro Ashina',
  ape: 'Guardian Ape',
  monkeys: 'Folding Screen Monkeys',
  headless_ape: 'Headless Ape',
  corrupted_monk: 'Corrupted Monk',
  owl: 'Great Shinobi - Owl',
  true_monk: 'Corrupted Monk - True Monk',
  divine_dragon: 'Divine Dragon',
  demon_of_hatred: 'Demon of Hatred',
  isshin: 'Isshin, the Sword Saint',
  emma: 'Emma, the Gentle Blade',
  isshin_ashina: 'Isshin Ashina',
};
export const BOSS_ALIASES = {headless: 'headless_ape', monk: 'corrupted_monk', truemonk: 'true_monk', dragon: 'divine_dragon', hatred: 'demon_of_hatred'};
export function evaluate(r) {
  r = {...r, boss: BOSS_ALIASES[r.boss] || r.boss};
  if (!Object.hasOwn(BOSSES, r.boss)) throw new Error("Choose a supported boss.");
  for (const [key, max] of [
    ["heals", 999],
    ["revives", 99],
  ])
    if (!Number.isInteger(r[key]) || r[key] < 0 || r[key] > max)
      throw new Error(
        "Enter whole numbers within the allowed ranges for healing and resurrections.",
      );
  for (const k of ["charmless", "bell", "prosthetic", "art", "cleared"])
    if (typeof r[k] !== "boolean")
      throw new Error("Valid challenge conditions are required.");
  if (!r.cleared) throw new Error("Only completed boss victories can be graded.");
  const score = Math.max(0, 100 - r.heals * 5 - r.revives * 15);
  const grade = score >= 95 ? "S" : score >= 80 ? "A" : score >= 60 ? "B" : "C";
  return {
    score,
    grade,
    title: {
      S: "Without hesitation",
      A: "An unwavering victory",
      B: "A blade that endured",
      C: "A hard-earned victory",
    }[grade],
    boss: BOSSES[r.boss],
  };
}
