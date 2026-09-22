export default function NotFound() {
  return (
    <main className="error-screen">
      <span className="eyebrow">TCSI Accounting</span>
      <h1>That page is not in this workspace.</h1>
      <p>The address may be out of date, or the workspace route has not been enabled yet.</p>
      <a className="button button--primary" href="/dashboard">
        Back to dashboard
      </a>
    </main>
  );
}
