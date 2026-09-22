import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "TCSI Accounting",
    template: "%s · TCSI Accounting",
  },
  description: "A calm, controlled workspace for modern finance teams.",
  applicationName: "TCSI Accounting",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
