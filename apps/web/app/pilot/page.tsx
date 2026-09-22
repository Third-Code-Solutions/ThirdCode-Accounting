import type { Metadata } from "next";

import { MarketingDetailPage } from "../../components/marketing-layout";

export const metadata: Metadata = {
  title: "Customer pilot",
  description: "See what a TCSI Accounting customer pilot covers from first review to a working close.",
};

export default function PilotPage() {
  return (
    <MarketingDetailPage
      active="/pilot"
      eyebrow="CUSTOMER PILOT"
      title="Start with the workflow your team already knows."
      intro="A TCSI pilot is a guided working session around your financial day. We map the records, roles, and review points that matter to your company before asking you to change the way you work."
      sections={[
        { eyebrow: "01 / Discover", title: "Bring the right questions.", copy: "We start with the way your team closes, reviews invoices, reconciles accounts, and hands work between people.", bullets: ["Current workflow and systems review", "Named business and implementation owners", "Pilot scope and success criteria"] },
        { eyebrow: "02 / Configure", title: "Shape the workspace around the work.", copy: "Accounts, journals, periods, access, and evidence rules are configured for the pilot environment, with synthetic data where appropriate.", bullets: ["Role and permission mapping", "Accounting structure and opening context", "Controlled sample data and acceptance checks"] },
        { eyebrow: "03 / Prove", title: "Use it with a real review cadence.", copy: "Your team works through representative tasks while we record what is clear, what needs adjusting, and what is ready for the next stage.", bullets: ["Daily activity and month-end scenarios", "Feedback captured with decisions", "A documented path to agreement"] },
      ]}
      asideTitle="Ready to see your workflow in it?"
      asideCopy="Tell us what your company needs to review. We will reply with a short, focused conversation rather than a generic product tour."
      asideLink="Request a demo"
      asideHref="/contact"
    />
  );
}
