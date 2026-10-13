import type { MetadataRoute } from "next";
import { SITE_URL } from "@/i18n/seo";

type Entry = {
  path: string;
  changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"];
  priority: number;
  /** false - у страницы пока нет казахской версии (юридические тексты). */
  kk?: boolean;
};

const PAGES: Entry[] = [
  { path: "", changeFrequency: "weekly", priority: 1.0 },
  { path: "/tracking", changeFrequency: "weekly", priority: 0.8 },
  { path: "/partners", changeFrequency: "monthly", priority: 0.7 },
  { path: "/privacy", changeFrequency: "yearly", priority: 0.3, kk: false },
  { path: "/terms", changeFrequency: "yearly", priority: 0.3, kk: false },
];

// Каждая языковая версия - отдельный <url> со ссылками друг на друга
// (xhtml:link hreflang), как рекомендует Google для многоязычных сайтов.
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return PAGES.flatMap(({ path, changeFrequency, priority, kk = true }) => {
    const ru = `${SITE_URL}${path || "/"}`;
    const kz = `${SITE_URL}/kz${path}`;
    const alternates = kk ? { languages: { "ru-KZ": ru, "kk-KZ": kz } } : undefined;
    const entries: MetadataRoute.Sitemap = [{ url: ru, lastModified: now, changeFrequency, priority, alternates }];
    if (kk) entries.push({ url: kz, lastModified: now, changeFrequency, priority, alternates });
    return entries;
  });
}
