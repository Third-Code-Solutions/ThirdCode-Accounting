import type { Metadata } from "next";

import { MarketingDetailPage } from "../../components/marketing-layout";

export const metadata: Metadata = {
  title: "Controls",
  description: "Learn how TCSI Accounting keeps roles, approvals, and audit evidence clear.",
};

export default function ControlsPage() {
  return (
    <MarketingDetailPage
      active="/controls"
      eyebrow="CONTROL WITHOUT THE CLUTTER"
      title="Clear roles. Reviewable actions. A stronger close."
      intro="A finance system has to do more than record a number. TCSI Accounting makes ownership, approvals, and audit evidence visible without turning everyday work into an obstacle course."
      sections={[
        { eyebrow: "Roles", title: "Give each person the right surface.", copy: "Separate company-owner oversight from operational accounting work. Assign members the access they need for their part of the process.", bullets: ["Administrator, Accountant, Encoder, and Read-only roles", "Separate audit-evidence reader access", "Company-scoped access rules on every record"] },
        { eyebrow: "Approvals", title: "Make the handoff explicit.", copy: "Draft work stays distinguishable from posted work. The next person can see what is waiting, who owns it, and what changed.", bullets: ["Draft and posting boundaries", "Closed-period protections", "Status and ownership in the work queue"] },
        { eyebrow: "Evidence", title: "Keep the trail with the record.", copy: "Audit events and source identifiers make it easier to explain how a number got there, when it moved, and what still needs sign-off.", bullets: ["Immutable audit event reads", "Source references on accounting records", "Posted records corrected by reversal, never edited"] },
      ]}
      asideTitle="Your books stay in your installation."
      asideCopy="Each client runs its own TCSI Accounting installation with its own database, files, and credentials. Your administrator manages your users; no other company shares your books."
      asideLink="See how rollout works"
      asideHref="/pilot"
    />
  );
}
