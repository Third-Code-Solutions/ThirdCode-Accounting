"use client";

import { ArrowRight, Check, LoaderCircle } from "lucide-react";
import { useState } from "react";

type FormState = {
  companyName: string;
  contactName: string;
  email: string;
  phone: string;
  teamSize: string;
  accountingStack: string;
  message: string;
  website: string;
};

const initialState: FormState = {
  companyName: "",
  contactName: "",
  email: "",
  phone: "",
  teamSize: "",
  accountingStack: "",
  message: "",
  website: "",
};

export function DemoRequestForm() {
  const [form, setForm] = useState<FormState>(initialState);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const update = (field: keyof FormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
    setError("");
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      const response = await fetch("/api/demo-requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const body = await response.json().catch(() => null) as { error?: { message?: string } } | null;
      if (!response.ok) {
        setError(body?.error?.message ?? "We could not submit the request. Please try again.");
        return;
      }
      setSubmitted(true);
      setForm(initialState);
    } catch {
      setError("We could not reach the request service. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  if (submitted) {
    return (
      <div className="demo-success" role="status" aria-live="polite">
        <span className="demo-success-icon"><Check aria-hidden="true" size={22} /></span>
        <p className="landing-kicker">REQUEST RECEIVED</p>
        <h2>Your demo request is in the TCSI intake queue.</h2>
        <p>We’ll review the details and reply to the email you provided with the next available time.</p>
        <button className="button button--quiet" type="button" onClick={() => setSubmitted(false)}>Send another request</button>
      </div>
    );
  }

  return (
    <form className="demo-form" onSubmit={submit} noValidate>
      <div className="demo-form-grid">
        <label className="demo-field">Company name<input value={form.companyName} onChange={(event) => update("companyName", event.target.value)} autoComplete="organization" placeholder="Your legal company name" minLength={2} maxLength={160} required /></label>
        <label className="demo-field">Your name<input value={form.contactName} onChange={(event) => update("contactName", event.target.value)} autoComplete="name" placeholder="Finance or operations lead" minLength={2} maxLength={120} required /></label>
        <label className="demo-field">Work email<input value={form.email} onChange={(event) => update("email", event.target.value)} autoComplete="email" inputMode="email" type="email" placeholder="you@company.com" maxLength={254} required /></label>
        <label className="demo-field">Phone <span>(optional)</span><input value={form.phone} onChange={(event) => update("phone", event.target.value)} autoComplete="tel" inputMode="tel" placeholder="+63 ..." maxLength={40} /></label>
        <label className="demo-field">Team size<select value={form.teamSize} onChange={(event) => update("teamSize", event.target.value)} required><option value="">Select a range</option><option value="1-5">1–5 people</option><option value="6-20">6–20 people</option><option value="21-50">21–50 people</option><option value="51-200">51–200 people</option><option value="201+">201+ people</option></select></label>
        <label className="demo-field">Current accounting system <span>(optional)</span><input value={form.accountingStack} onChange={(event) => update("accountingStack", event.target.value)} placeholder="What you use today" maxLength={160} /></label>
      </div>
      <label className="demo-field">What would you like to see?<textarea value={form.message} onChange={(event) => update("message", event.target.value)} placeholder="Tell us about your close, review, or reporting workflow." minLength={10} maxLength={2000} rows={5} required /></label>
      <label className="demo-honeypot" aria-hidden="true">Website<input tabIndex={-1} autoComplete="off" value={form.website} onChange={(event) => update("website", event.target.value)} /></label>
      {error && <p className="form-message form-message--error" role="alert">{error}</p>}
      <div className="demo-form-footer">
        <p>We only use these details to respond to this request.</p>
        <button className="landing-button landing-button--primary" type="submit" disabled={busy}>{busy ? <><LoaderCircle className="demo-spinner" aria-hidden="true" size={16} /> Sending…</> : <>Request a demo <ArrowRight aria-hidden="true" size={16} /></>}</button>
      </div>
    </form>
  );
}
