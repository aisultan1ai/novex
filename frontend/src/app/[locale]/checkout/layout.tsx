import type { ReactNode } from "react";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";

import { CHECKOUT_NAMESPACES, pickMessages } from "@/i18n/messages";

// Оплата: публичные переводы + checkout и шаги оформления.
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
    <NextIntlClientProvider messages={pickMessages(messages, CHECKOUT_NAMESPACES)}>
      {children}
    </NextIntlClientProvider>
  );
}
