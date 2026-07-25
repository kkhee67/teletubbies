import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

const title = "안심계약 레이더";
const description =
  "주소와 보증금으로 시작해 전세계약의 확인된 위험과 미확인 정보를 구분해 보여주는 계약 전 의사결정 지원 서비스";

export async function generateMetadata(): Promise<Metadata> {
  const headerStore = await headers();
  const forwardedHost =
    headerStore.get("x-forwarded-host") ?? headerStore.get("host");
  const host = forwardedHost?.split(",")[0].trim() || "localhost:3000";
  const forwardedProtocol = headerStore.get("x-forwarded-proto");
  const protocol =
    forwardedProtocol?.split(",")[0].trim() ||
    (host.startsWith("localhost") ? "http" : "https");
  let metadataBase: URL;

  try {
    metadataBase = new URL(`${protocol}://${host}`);
  } catch {
    metadataBase = new URL("http://localhost:3000");
  }

  const socialImage = new URL("/og.png", metadataBase).toString();

  return {
    title,
    description,
    metadataBase,
    openGraph: {
      title,
      description,
      images: [{ url: socialImage, width: 1536, height: 1024, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [socialImage],
    },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
