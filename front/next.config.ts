import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 개발 서버와 build가 같은 .next를 쓰면, build가 개발 서버의 chunk를 덮어써서
  // 새로고침할 때 "__webpack_modules__[moduleId] is not a function"이 난다.
  // 개발 서버를 켜 둔 채 build로 확인할 때는 NEXT_DIST_DIR=.next-build를 준다.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
};

export default nextConfig;
