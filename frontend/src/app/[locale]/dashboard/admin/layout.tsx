import type { ReactNode } from "react";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";
import AdminShell from "@/components/admin/AdminShell";
import { ADMIN_NAMESPACES, pickMessages } from "@/i18n/messages";

// Админка: всё из кабинета + admin. Оболочка (вкладки, mobile-ограничение) — AdminShell.

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
    <NextIntlClientProvider messages={pickMessages(messages, ADMIN_NAMESPACES)}>
      <AdminShell>{children}</AdminShell>
    </NextIntlClientProvider>
  );
}
