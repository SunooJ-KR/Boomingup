import "server-only";

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * 팀 규칙상 키와 DB URL은 저장소 루트 .env에 있다(docs/railway-postgres-onboarding.md).
 * front/.env.local에 같은 값을 또 적지 않아도 되게 루트 .env를 읽어 준다.
 * 배포 환경에서는 process.env가 먼저다.
 */
export function readRootEnv(name: string): string | undefined {
  if (process.env[name]) return process.env[name];
  try {
    const text = readFileSync(resolve(process.cwd(), "..", ".env"), "utf8");
    const matched = new RegExp(`^${name}=(.*)$`, "m").exec(text);
    return matched?.[1]?.trim().replace(/^"|"$/g, "") || undefined;
  } catch {
    return undefined;
  }
}
