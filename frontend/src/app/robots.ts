import type { MetadataRoute } from "next";
import { SITE_URL } from "@/i18n/seo";

// Закрытые разделы - для обеих языковых версий (/... и /kz/...).
const PRIVATE = [
  "/dashboard/",
  "/checkout/",
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", ...PRIVATE, ...PRIVATE.map((p) => `/kz${p}`)],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
