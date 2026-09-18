import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

export default function nextConfig(phase: string): NextConfig {
  return {
    // Next.js 15는 dev와 build가 기본적으로 같은 .next를 써서 동시에 실행하면
    // 개발 서버가 이미 읽은 webpack 청크와 디스크의 청크가 어긋날 수 있다.
    // Vercel은 production 산출물을 기본 경로인 .next에서 찾으므로 dev만 분리한다.
    distDir: phase === PHASE_DEVELOPMENT_SERVER ? ".next-dev" : ".next",
  };
}
