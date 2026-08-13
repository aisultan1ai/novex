import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Отслеживание посылок",
  description:
    "Отследите статус посылки по трек-номеру Novex, Azimuth Cargo, Exline или CSE — вся информация в одном окне.",
  alternates: { canonical: "/tracking" },
};

export default function TrackingLayout({ children }: { children: ReactNode }) {
  return children;
}
