import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

import { AuthProvider } from "@/components/providers/auth-provider";

const SITE_URL = "https://novex.kz";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Novex — Доставка по Казахстану",
    template: "%s — Novex",
  },
  description:
    "Novex — агрегатор курьерских служб Казахстана. Сравните тарифы Azimuth Cargo, Exline, CSE и оформите доставку онлайн за 2 минуты.",
  applicationName: "Novex",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "ru_KZ",
    url: SITE_URL,
    siteName: "Novex",
    title: "Novex — Доставка по Казахстану",
    description:
      "Сравните тарифы курьерских служб Казахстана и оформите отправление за 2 минуты.",
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

export const viewport: Viewport = {
  themeColor: "#0B2545",
};

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
  url: SITE_URL,
  potentialAction: {
    "@type": "SearchAction",
    target: `${SITE_URL}/tracking?query={search_term_string}`,
    "query-input": "required name=search_term_string",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
        />
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
