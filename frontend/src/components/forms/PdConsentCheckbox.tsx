"use client";

import type { ReactNode } from "react";
import { useLocale, useTranslations } from "next-intl";

import { localePrefix } from "@/i18n/routing";

/**
 * Personal-data consent checkbox (KZ «О персональных данных и их защите»).
 * Links open in a new tab so the half-filled form is not lost.
 */
export default function PdConsentCheckbox({
  checked,
  onChange,
  children,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  children?: ReactNode;
}) {
  const t = useTranslations("consent");
  const prefix = localePrefix(useLocale());
  return (
    <label style={{ display: "flex", gap: 10, alignItems: "flex-start", cursor: "pointer", font: "400 13px/1.5 Inter Variable, sans-serif", color: "#475569" }}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        style={{ width: 18, height: 18, marginTop: 1, flexShrink: 0, accentColor: "#0B2545", cursor: "pointer" }}
      />
      <span>
        {children ?? t("default")}{" "}
        {t.rich("links", {
          privacy: (c) => (
            <a href={`${prefix}/privacy`} target="_blank" rel="noopener noreferrer" style={{ color: "#0E2E5C", textDecoration: "underline" }}>
              {c}
            </a>
          ),
          terms: (c) => (
            <a href={`${prefix}/terms`} target="_blank" rel="noopener noreferrer" style={{ color: "#0E2E5C", textDecoration: "underline" }}>
              {c}
            </a>
          ),
        })}
      </span>
    </label>
  );
}
