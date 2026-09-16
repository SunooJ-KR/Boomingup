/** "2026Q2" 같은 분기 문자열을 다룬다. */

export function parseQuarter(quarter: string): { year: number; q: number } | null {
  const match = /^(\d{4})Q([1-4])$/.exec(quarter);
  if (!match) return null;
  return { year: Number(match[1]), q: Number(match[2]) };
}

/** delta 분기만큼 이동한다. shiftQuarter("2026Q2", -4) === "2025Q2" */
export function shiftQuarter(quarter: string, delta: number): string {
  const parsed = parseQuarter(quarter);
  if (!parsed) return quarter;
  const total = parsed.year * 4 + (parsed.q - 1) + delta;
  const year = Math.floor(total / 4);
  const q = (total % 4) + 1;
  return `${year}Q${q}`;
}
