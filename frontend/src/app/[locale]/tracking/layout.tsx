import type { Metadata } from "next";
import type { ReactNode } from "react";
import { getTranslations } from "next-intl/server";

import { localeAlternates } from "@/i18n/seo";

type Props = { children: ReactNode; params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "meta.tracking" });
  return {
    title: t("title"),
    description: t("description"),
    alternates: localeAlternates("/tracking", locale),
  };
}

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
