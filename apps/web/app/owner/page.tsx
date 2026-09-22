import type { Metadata } from "next";

import { PlatformOwnerView } from "../../components/platform-owner-view";
import { loadPlatformOwnerSummary } from "../../lib/platform-owner";

export const metadata: Metadata = {
  title: "Platform owner console",
  description: "Private TCSI product and tenant analytics.",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

export default async function OwnerPage() {
  const summary = await loadPlatformOwnerSummary();
  return <PlatformOwnerView summary={summary} />;
}
