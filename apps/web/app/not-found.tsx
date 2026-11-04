export default function NotFound() {
  return (
    <main className="error-screen">
      <span className="eyebrow">TCSI Accounting</span>
      <h1>We could not find that page.</h1>
      <p>The address may be mistyped or out of date.</p>
      <a className="button button--primary" href="/">
        Back to home
      </a>
    </main>
  );
}
