import { redirect } from "next/navigation";
import { isPilotPortal } from "../lib/pilot";

export default function HomePage() {
  if (isPilotPortal()) {
    const pilotUrl = process.env.TCSI_PILOT_URL;
    return (
      <main className="pilot-portal">
        <header><strong>TCSI</strong><span>Third Code Solutions Inc.</span></header>
        <section aria-labelledby="portal-title">
          <p className="eyebrow">Customer pilot · invitation only</p>
          <h1 id="portal-title">Your accounting workspace.</h1>
          <p>Access the TCSI Accounting pilot with the credentials assigned by your implementation team.</p>
          {pilotUrl ? <a className="button button--primary" href={pilotUrl}>Open accounting workspace →</a> : <p role="status">Workspace access is being configured. Please contact your implementation team.</p>}
          <aside><h2>About this release</h2><p>This portal is separate from your accounting workspace. The new standalone accounting platform is in development and is not available for financial transactions.</p><p>Use evaluation data during the pilot. Real company records require an approved onboarding and data-protection plan.</p></aside>
        </section>
        <footer><span>Third Code Solutions Inc.</span><a href="https://www.thirdcodesolutions.com">Company website ↗</a></footer>
      </main>
    );
  }
  redirect("/dashboard");
}
