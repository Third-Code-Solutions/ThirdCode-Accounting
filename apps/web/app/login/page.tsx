import type { Metadata } from "next";

import { LoginForm } from "../../components/login-form";
import { isPilotPortal } from "../../lib/pilot";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to TCSI Accounting.",
  robots: { index: false, follow: false },
};

export default function LoginPage() {
  return <LoginForm pilotPortal={isPilotPortal()} />;
}
