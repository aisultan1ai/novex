import type { ReactNode } from "react";
import "./globals.css";

// <html>/<body> рендерит app/[locale]/layout.tsx, чтобы lang="ru" | "kk"
// соответствовал языку страницы. Этот корневой layout только подключает стили.
export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
