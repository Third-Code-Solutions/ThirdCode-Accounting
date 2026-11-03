"use client";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="error-screen">
      <span className="eyebrow">TCSI Accounting</span>
      <h1>We hit a temporary issue.</h1>
      <p>Nothing was changed. Try the page again, or return to the home page.</p>
      <div className="inline-actions">
        <button className="button button--primary" type="button" onClick={reset}>
          Try again
        </button>
        <a className="button button--quiet" href="/">
          Back to home
        </a>
      </div>
    </main>
  );
}
