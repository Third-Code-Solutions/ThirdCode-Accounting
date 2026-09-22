import type { Metadata } from "next";

import { MarketingDetailPage } from "../../components/marketing-layout";

export const metadata: Metadata = {
  title: "Platform",
  description: "See how TCSI Accounting connects ledger work, invoicing, reconciliation, and reporting.",
};

export default function PlatformPage() {
  return (
    <MarketingDetailPage
      active="/platform"
      eyebrow="THE TCSI PLATFORM"
      title="The accounting workbench for the whole financial day."
      intro="TCSI Accounting gives finance teams one controlled place to prepare entries, follow invoices, reconcile activity, and understand what is ready for close. It is built for the work between a source document and a decision."
      sections={[
        { eyebrow: "Ledger", title: "Prepare and post with context.", copy: "Keep journals, periods, accounts, and entry evidence connected so a reviewer can understand the movement without opening five systems.", bullets: ["Chart of accounts and journal structure", "Draft, posted, and void states", "Period controls and balanced entry checks"] },
        { eyebrow: "Receivables", title: "Know what is owed and what needs action.", copy: "Track customer invoices from draft through payment, with the counterparty and balance due visible beside the work queue.", bullets: ["Sales, purchase, credit, and debit invoices", "Customer and supplier records", "Payment status and outstanding balances"] },
        { eyebrow: "Close", title: "Turn review into a repeatable rhythm.", copy: "Move from daily activity to month-end confidence with focused reports, reconciliation evidence, and a visible next step for every open item.", bullets: ["Open-period visibility", "Bank and cash review workflows", "Exportable, reviewable financial views"] },
      ]}
      asideTitle="Built for decisions, not data entry."
      asideCopy="The product keeps the operational view close to the accounting record, so people can work from the same version of the truth."
      asideLink="See the control model"
      asideHref="/controls"
    />
  );
}
