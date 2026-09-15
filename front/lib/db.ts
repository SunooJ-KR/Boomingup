import "server-only";

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { Pool } from "pg";

/**
 * 읽기 전용 계정으로만 접속한다. docs/railway-postgres-onboarding.md 참고.
 * URL이 없으면 null을 돌려주고, 호출하는 쪽이 샘플 JSON으로 폴백한다.
 */
let pool: Pool | null | undefined;

function readUrl(): string | undefined {
  if (process.env.DATABASE_READONLY_URL) return process.env.DATABASE_READONLY_URL;
  // 팀 규칙상 DB URL은 저장소 루트 .env에 있다. front/.env.local을 따로 만들지 않아도 되게 한 번 읽는다.
  try {
    const text = readFileSync(resolve(process.cwd(), "..", ".env"), "utf8");
    return /^DATABASE_READONLY_URL=(.*)$/m
      .exec(text)?.[1]
      ?.trim()
      .replace(/^"|"$/g, "");
  } catch {
    return undefined;
  }
}

export function getPool(): Pool | null {
  if (pool !== undefined) return pool;
  const connectionString = readUrl();
  pool = connectionString
    ? new Pool({ connectionString, max: 4, statement_timeout: 10_000 })
    : null;
  return pool;
}

export async function query<T>(text: string, params: unknown[] = []): Promise<T[]> {
  const activePool = getPool();
  if (!activePool) throw new Error("DATABASE_READONLY_URL이 없습니다.");
  const result = await activePool.query(text, params);
  return result.rows as T[];
}
