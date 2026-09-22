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
        { eyebrow: "Roles", title: "Give each person the right surface.", copy: "Separate company-owner oversight from operational accounting work. Assign members the access they need for their part of the process.", bullets: ["Owner, admin, accountant, encoder, and viewer roles", "Tenant-scoped access policies", "Separate platform-owner control plane"] },
        { eyebrow: "Approvals", title: "Make the handoff explicit.", copy: "Draft work stays distinguishable from posted work. The next person can see what is waiting, who owns it, and what changed.", bullets: ["Draft and posting boundaries", "Closed-period protections", "Status and ownership in the work queue"] },
        { eyebrow: "Evidence", title: "Keep the trail with the record.", copy: "Audit events and source identifiers make it easier to explain how a number got there, when it moved, and what still needs sign-off.", bullets: ["Immutable audit event reads", "Source references on accounting records", "Tenant data protected by database policies"] },
      ]}
      asideTitle="Customer owners see their company."
      asideCopy="A customer organization owner can manage that organization’s workspace and members, but cannot see another customer’s books or the TCSI product console."
      asideLink="Understand the pilot"
      asideHref="/pilot"
    />
  );
}
