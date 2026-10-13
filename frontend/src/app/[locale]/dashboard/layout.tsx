import type { ReactNode } from "react";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";
import DashboardShell from "@/components/layout/DashboardShell";
import { DASHBOARD_NAMESPACES, pickMessages } from "@/i18n/messages";

// Кабинеты: публичные переводы + dashboard/carrier/статусы. Оболочка (шапка, вкладки) — DashboardShell.
import type { Metadata } from "next";

// Служебные шаги оформления не индексируются и не объявляют canonical/hreflang.
export const metadata: Metadata = { robots: { index: false, follow: false } };

export default async function Layout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const messages = await getMessages();
  return (
    <NextIntlClientProvider messages={pickMessages(messages, DASHBOARD_NAMESPACES)}>
      <DashboardShell>{children}</DashboardShell>
    </NextIntlClientProvider>
  );
}
