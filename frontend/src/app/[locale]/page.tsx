import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";

import HomePage from "@/components/home/HomePage";
import { localeAlternates } from "@/i18n/seo";

type Props = { params: Promise<{ locale: string }> };

// canonical/hreflang объявляют только индексируемые страницы (главная,
// отслеживание, партнёрам, юридические) — не общий layout.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  return { alternates: localeAlternates("/", locale) };
}

export default async function Page({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <HomePage />;
}
