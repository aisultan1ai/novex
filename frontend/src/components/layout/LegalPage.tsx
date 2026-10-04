import type { ReactNode } from "react";

import Footer from "@/components/layout/Footer";
import Navbar from "@/components/layout/Navbar";
import { CONTACTS } from "@/lib/config/contacts";

// Company details shown on legal pages. Fill in the legal entity (ТОО / ИП),
// БИН / ИИН and address here once they are available — both pages pick them up.
export const LEGAL_ENTITY = {
  name: "NOVEX",
  email: CONTACTS.supportEmail,
  site: "novex.kz",
};

export interface LegalSection {
  title: string;
  body: ReactNode;
}

export default function LegalPage({
  title,
  updatedAt,
  intro,
  sections,
}: {
  title: string;
  updatedAt: string;
  intro: ReactNode;
  sections: LegalSection[];
}) {
  return (
    <>
      <Navbar />
      <main style={{ background: "#F7F9FB", padding: "48px 16px 80px" }}>
        <article
          style={{
            maxWidth: 820,
            margin: "0 auto",
            background: "#ffffff",
            border: "1px solid #E2E8EE",
            borderRadius: 16,
            padding: "clamp(20px, 5vw, 48px)",
            color: "#1E2A38",
            font: "400 15px/1.7 Inter Variable, sans-serif",
          }}
        >
          <h1 style={{ margin: "0 0 8px", font: "700 clamp(24px, 4vw, 32px)/1.2 'Space Grotesk Variable', 'Inter Variable', sans-serif", color: "#0B2545" }}>
            {title}
          </h1>
          <p style={{ margin: "0 0 28px", fontSize: 13, color: "#64748b" }}>Редакция от {updatedAt}</p>
          <div style={{ marginBottom: 28 }}>{intro}</div>
          {sections.map((s, i) => (
            <section key={s.title} style={{ marginBottom: 24 }}>
              <h2 style={{ margin: "0 0 10px", fontSize: 18, fontWeight: 700, color: "#0B2545" }}>
                {i + 1}. {s.title}
              </h2>
              <div>{s.body}</div>
            </section>
          ))}
          <p style={{ marginTop: 32, paddingTop: 20, borderTop: "1px solid #E2E8EE", fontSize: 14, color: "#475569" }}>
            {LEGAL_ENTITY.name} · <a href={`mailto:${LEGAL_ENTITY.email}`} style={{ color: "#0E2E5C" }}>{LEGAL_ENTITY.email}</a> · {LEGAL_ENTITY.site}
          </p>
        </article>
      </main>
      <Footer />
    </>
  );
}
