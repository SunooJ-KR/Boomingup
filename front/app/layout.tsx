import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Boomingup",
  description: "서울 법정동별 추정 변화율과 관측 정보를 한 화면에서 볼 수 있어요.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
