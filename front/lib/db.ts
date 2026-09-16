import "server-only";

import { Pool } from "pg";

import { readRootEnv } from "./root-env";

/**
 * 읽기 전용 계정으로만 접속한다. docs/railway-postgres-onboarding.md 참고.
 * URL이 없으면 null을 돌려주고, 호출하는 쪽이 샘플 JSON으로 폴백한다.
 */
let pool: Pool | null | undefined;

export function getPool(): Pool | null {
  if (pool !== undefined) return pool;
  const connectionString = readRootEnv("DATABASE_READONLY_URL");
  pool = connectionString ? new Pool({ connectionString, max: 4, statement_timeout: 10_000 }) : null;
  return pool;
}

export async function query<T>(text: string, params: unknown[] = []): Promise<T[]> {
  const activePool = getPool();
  if (!activePool) throw new Error("DATABASE_READONLY_URL이 없습니다.");
  const result = await activePool.query(text, params);
  return result.rows as T[];
}
