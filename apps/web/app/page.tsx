import type { Metadata } from "next";

import { LandingPage } from "../components/landing-page";
import { siteOrigin } from "../lib/site";
import { loadPublicContent } from "../lib/public-content";

const defaultMetadata: Metadata = {
  title: { absolute: "TCSI Accounting | Clarity for every financial decision" },
  description: "Connect invoices, bills, banking, expenses, financial reports, and accounting controls in one TCSI workspace. Request a demo for your company.",
  alternates: { canonical: siteOrigin() },
  openGraph: {
    title: "TCSI Accounting | Clarity for every financial decision",
    description: "One connected workspace for your financial day. Explore accounting, reporting, and controls built around your team.",
    url: siteOrigin(),
    type: "website",
  },
};

export async function generateMetadata(): Promise<Metadata> {
  const { seo } = await loadPublicContent();
  if (!seo) return defaultMetadata;
  return { ...defaultMetadata, title: { absolute: seo.title }, description: seo.description,
    openGraph: { ...defaultMetadata.openGraph, title: seo.title, description: seo.description } };
}

export const dynamic = "force-dynamic";

export default function HomePage() {
  return <LandingPage />;
}
