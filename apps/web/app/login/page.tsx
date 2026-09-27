import type { Metadata } from "next";

import { LoginForm } from "../../components/login-form";
import { isPilotPortal } from "../../lib/pilot";

export const metadata: Metadata = {
  title: "Sign in",
};

export default function LoginPage() {
  return <LoginForm pilotPortal={isPilotPortal()} />;
}
