import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter } from "next/font/google";

import { AuthProvider } from "@/components/providers/auth-provider";

const inter = Inter({
  subsets: ["latin", "cyrillic"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Novex — Доставка по Казахстану",
  description:
    "Сравните тарифы курьерских служб и оформите доставку онлайн",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru" className={inter.variable}>
      <body
        style={{
          margin: 0,
          fontFamily:
            "var(--font-inter), Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
          WebkitFontSmoothing: "antialiased",
        }}
      >
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
