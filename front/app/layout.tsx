import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Boomingup",
  description: "서울 법정동 단위의 추정 변화율과 관측 정보를 함께 보는 화면",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
