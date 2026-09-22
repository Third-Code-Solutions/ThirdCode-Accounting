import type { Metadata } from "next";

import { DemoRequestForm } from "../../components/demo-request-form";
import { MarketingShell } from "../../components/marketing-layout";

export const metadata: Metadata = {
  title: "Request a demo",
  description: "Tell Third Code Solutions Inc. how your company handles accounting and request a TCSI Accounting demo.",
};

export default function ContactPage() {
  return (
    <MarketingShell active="/contact">
      <section className="contact-hero" aria-labelledby="contact-title">
        <div>
          <p className="landing-kicker"><span /> TALK TO TCSI</p>
          <h1 id="contact-title">Show us the work behind your numbers.</h1>
          <p className="marketing-hero-intro">A real company can request a product demo here. Share a little context about your team and we’ll come prepared to discuss the workflow, controls, and reporting you actually need.</p>
          <div className="contact-notes" aria-label="What happens next">
            <div><strong>01</strong><span>We review the company and workflow details.</span></div>
            <div><strong>02</strong><span>We reply to your work email with next steps.</span></div>
            <div><strong>03</strong><span>We run a focused demo around your use case.</span></div>
          </div>
        </div>
        <div className="contact-form-panel">
          <p className="landing-kicker">REQUEST A DEMO</p>
          <h2>Tell us where to start.</h2>
          <DemoRequestForm />
        </div>
      </section>
    </MarketingShell>
  );
}
