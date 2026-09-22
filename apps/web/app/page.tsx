import { redirect } from "next/navigation";

import { LandingPage } from "../components/landing-page";
import { isPilotPortal } from "../lib/pilot";

export const dynamic = "force-dynamic";

export default function HomePage() {
  if (isPilotPortal()) {
    return <LandingPage />;
  }
  redirect("/dashboard");
}
