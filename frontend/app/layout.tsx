import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "안심계약 레이더",
  description: "주소와 보증금으로 시작해 전세계약의 확인된 위험과 미확인 정보를 구분해 보여주는 계약 전 의사결정 지원 서비스",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
