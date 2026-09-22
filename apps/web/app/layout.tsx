import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "TCSI Accounting",
    template: "%s · TCSI Accounting",
  },
  description: "A calm, controlled workspace for modern finance teams.",
  applicationName: "TCSI Accounting",
  openGraph: {
    title: "TCSI Accounting · Clear books, clear next steps",
    description: "A focused accounting workspace for finance teams that need a clearer operating view.",
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
