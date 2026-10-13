import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";

import { AuthProvider } from "@/components/providers/auth-provider";
import LocaleSync from "@/components/providers/LocaleSync";
import { pickMessages, PUBLIC_NAMESPACES } from "@/i18n/messages";
import { routing } from "@/i18n/routing";
import { OG_LOCALE, SITE_URL } from "@/i18n/seo";

type Props = { children: ReactNode; params: Promise<{ locale: string }> };

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "meta" });
  return {
    metadataBase: new URL(SITE_URL),
    title: { default: t("title"), template: `%s — Novex` },
    description: t("description"),
    applicationName: "Novex",
    openGraph: {
      type: "website",
      locale: OG_LOCALE[locale],
      alternateLocale: Object.values(OG_LOCALE).filter((l) => l !== OG_LOCALE[locale]),
      url: SITE_URL,
      siteName: "Novex",
      title: t("title"),
      description: t("ogDescription"),
    },
    icons: {
      icon: [
        { url: "/favicon.svg", type: "image/svg+xml" },
        { url: "/favicon.ico", sizes: "any" },
        { url: "/favicon-32.png", sizes: "32x32", type: "image/png" },
        { url: "/favicon-192.png", sizes: "192x192", type: "image/png" },
        { url: "/favicon-512.png", sizes: "512x512", type: "image/png" },
      ],
      apple: [{ url: "/favicon-180.png", sizes: "180x180", type: "image/png" }],
    },
  };
}

export const viewport: Viewport = {
  themeColor: "#0B2545",
};

export default async function LocaleLayout({ children, params }: Props) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  const messages = await getMessages();

  const prefix = locale === "kk" ? "/kz" : "";
  const organizationJsonLd = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Novex",
    url: SITE_URL,
    logo: `${SITE_URL}/favicon-512.png`,
    email: "support@novex.kz",
    areaServed: "KZ",
  };
  const websiteJsonLd = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Novex",
    url: `${SITE_URL}${prefix}`,
    inLanguage: locale === "kk" ? "kk-KZ" : "ru-KZ",
    potentialAction: {
      "@type": "SearchAction",
      target: `${SITE_URL}${prefix}/tracking?query={search_term_string}`,
      "query-input": "required name=search_term_string",
    },
  };

  return (
    <html lang={locale}>
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
        />
        <NextIntlClientProvider messages={pickMessages(messages, PUBLIC_NAMESPACES)}>
          <LocaleSync locale={locale} />
          <AuthProvider>{children}</AuthProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
