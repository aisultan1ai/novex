import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

import { AuthProvider } from "@/components/providers/auth-provider";

export const metadata: Metadata = {
  title: "Novex - Доставка по Казахстану",
  description:
    "Сравните тарифы курьерских служб и оформите доставку онлайн",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
