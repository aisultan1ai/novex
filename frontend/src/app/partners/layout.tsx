import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Партнёрам",
  description:
    "Подключите свою курьерскую службу к агрегатору Novex — приведём заказы из Казахстана без затрат на маркетинг.",
  alternates: { canonical: "/partners" },
};

export default function PartnersLayout({ children }: { children: ReactNode }) {
  return children;
}
