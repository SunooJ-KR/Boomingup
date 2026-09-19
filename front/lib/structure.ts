/** 구조 유형은 순서나 높낮이가 없는 범주라 서로 다른 색으로 구분한다. */
export const STRUCTURE_BG_CLASSES = [
  "bg-structure-0",
  "bg-structure-1",
  "bg-structure-2",
  "bg-structure-3",
] as const;

export const STRUCTURE_TEXT_CLASSES = [
  "text-structure-0",
  "text-structure-1",
  "text-structure-2",
  "text-structure-3",
] as const;

export function structureBackgroundClass(type: number | null): string {
  return type === null ? "bg-neutral-strong" : (STRUCTURE_BG_CLASSES[type] ?? "bg-neutral-strong");
}

export function structureTextClass(type: number | null): string {
  return type === null ? "text-foreground" : (STRUCTURE_TEXT_CLASSES[type] ?? "text-foreground");
}
