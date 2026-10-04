import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "TCSI Accounting",
    template: "%s · TCSI Accounting",
  },
  description: "TCSI Accounting connects ledger work, invoicing, reconciliation, controls, and reporting in one clear workspace for finance teams.",
  applicationName: "TCSI Accounting",
  icons: {
    icon: ["/favicon.ico", "/icon.svg"],
    shortcut: "/favicon.ico",
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    title: "TCSI Accounting · Clear books, clear next steps",
    description: "Prepare entries, follow invoices, reconcile activity, and see what is ready for close in a controlled TCSI workspace.",
    type: "website",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
