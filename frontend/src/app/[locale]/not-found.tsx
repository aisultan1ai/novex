import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";

export default async function NotFound() {
  const t = await getTranslations("notFound");
  return (
    <main style={{ minHeight: "70vh", display: "grid", placeItems: "center", padding: 24, textAlign: "center" }}>
      <div>
        <div style={{ font: "700 64px/1 'Space Grotesk Variable', 'Inter Variable', sans-serif", color: "#0B2545" }}>404</div>
        <h1 style={{ font: "600 24px/1.3 'Inter Variable', sans-serif", color: "#0E1826", margin: "16px 0 8px" }}>{t("title")}</h1>
        <p style={{ font: "400 15px/1.6 'Inter Variable', sans-serif", color: "#5F6E7E", margin: "0 0 24px" }}>{t("text")}</p>
        <Link href="/" style={{ display: "inline-block", background: "#0B2545", color: "#fff", padding: "12px 22px", borderRadius: 10, font: "600 15px/1 'Inter Variable', sans-serif", textDecoration: "none" }}>
          {t("home")}
        </Link>
      </div>
    </main>
  );
}
