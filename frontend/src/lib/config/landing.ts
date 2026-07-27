// Marketing numbers shown on the landing page hero. Values come from
// NEXT_PUBLIC_* env vars so ops can bump them without a code push; sensible
// defaults keep local/dev builds truthful (all lowercased "TBD" would look
// like a broken build).
//
// To change in production:
//   .env:
//     NEXT_PUBLIC_STAT_CARRIERS_LABEL="10+"
//     NEXT_PUBLIC_STAT_SHIPMENTS_LABEL="50 000+"
//     NEXT_PUBLIC_STAT_RATING_LABEL="5.0 ★"
//
// NEXT_PUBLIC_ prefix is required (otherwise Next.js strips the value from
// the client bundle). A rebuild is needed after editing .env.

export const LANDING_STATS = {
  carriersLabel: process.env.NEXT_PUBLIC_STAT_CARRIERS_LABEL || "3+",
  shipmentsLabel: process.env.NEXT_PUBLIC_STAT_SHIPMENTS_LABEL || "",
  ratingLabel: process.env.NEXT_PUBLIC_STAT_RATING_LABEL || "",
} as const;

// Carriers we currently integrate with. This drives both the "trusted-by"
// strip and any counts on the landing page — keep it as the single source of
// truth so we cannot claim "10+" while showing 3 logos below.
export interface SupportedCarrier {
  code: string;         // lower-case internal code
  name: string;         // display label
  logo: string;         // path under /public
}

export const SUPPORTED_CARRIERS: readonly SupportedCarrier[] = [
  { code: "azimuth", name: "Azimuth Cargo", logo: "/carriers/azimuth.png" },
  { code: "exline",  name: "Exline",        logo: "/carriers/exline.svg"  },
  { code: "cse",     name: "CSE",           logo: "/carriers/cse.png"     },
] as const;
