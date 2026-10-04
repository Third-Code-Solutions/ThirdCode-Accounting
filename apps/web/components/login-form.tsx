"use client";

import { ArrowRight, Check, Eye, EyeOff, LockKeyhole, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type AuthChangeEvent } from "@supabase/supabase-js";
import { useEffect, useState } from "react";

import { getPublicEnv } from "../lib/env";
import { getSupabaseBrowserClient } from "../lib/supabase/browser";

type AuthMode = "signin" | "reset" | "update";

export function LoginForm({ pilotPortal }: { pilotPortal: boolean }) {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const configured = getPublicEnv().supabaseConfigured;

  useEffect(() => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) return;
    // Recovery links arrive as ?mode=update (server token-hash confirmation),
    // ?code=… (PKCE flow) or #access_token=…&type=recovery (implicit flow).
    // All three settle on this page. The state updates ride the auth
    // subscription callbacks, so first paint stays hydration-safe.
    const params = new URLSearchParams(window.location.search);
    const recoveryLanding =
      params.get("mode") === "update" ||
      params.get("type") === "recovery" ||
      params.has("code") ||
      window.location.hash.includes("type=recovery");
    const linkInvalid = params.get("state") === "link_invalid";

    const { data } = supabase.auth.onAuthStateChange((event: AuthChangeEvent) => {
      if (event === "INITIAL_SESSION") {
        if (linkInvalid) {
          setError("That link has expired or has already been used. Request a new one below.");
        }
        if (recoveryLanding) {
          setMode("update");
        }
        return;
      }
      if (event === "PASSWORD_RECOVERY" || (recoveryLanding && event === "SIGNED_IN")) {
        setMode("update");
        setError("");
        setMessage("");
      }
    });
    return () => data.subscription.unsubscribe();
  }, []);

  const destination = pilotPortal ? "/owner" : "/dashboard";

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");

    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      setBusy(false);
      setError("Supabase is not connected in this environment yet. Add the publishable project values, then try again.");
      return;
    }

    if (mode === "update") {
      if (password !== confirmPassword) {
        setBusy(false);
        setError("The two passwords do not match.");
        return;
      }
      const updated = await supabase.auth.updateUser({ password });
      setBusy(false);
      if (updated.error) {
        setError(updated.error.message);
        return;
      }
      setMessage("Password saved. Opening your console…");
      router.push(destination);
      return;
    }

    const result = mode === "signin"
      ? await supabase.auth.signInWithPassword({ email, password })
      : await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${window.location.origin}/login` });

    setBusy(false);
    if (result.error) {
      setError(result.error.message);
      return;
    }

    if (mode === "signin") {
      router.push(destination);
    } else {
      setMessage("If that email belongs to a TCSI account, a reset link is on its way.");
    }
  };

  const title = mode === "signin" ? "Welcome back" : mode === "update" ? "Set a new password" : "Reset your password";
  const submitLabel = mode === "signin" ? "Sign in" : mode === "update" ? "Save new password" : "Send reset link";

  return (
    <main className="auth-page">
      <section className="auth-visual" aria-label="TCSI Accounting product overview">
        <div className="auth-visual-top"><span className="brand-mark">T</span><span>TCSI Accounting</span></div>
        <div className="auth-visual-copy">
          <span className="eyebrow">Finance, made clear</span>
          <h1>Confident books.<br /><em>Decisive</em> action.</h1>
          <p>A calm, focused workspace for the people who keep a business moving.</p>
        </div>
        <div className="auth-visual-card">
          <div className="auth-card-label"><span>Workspace pulse</span><span className="live-label"><i /> Live</span></div>
          <div className="auth-sparkline"><span /><span /><span /><span /><span /><span /><span /></div>
          <div className="auth-card-footer"><span>Review</span><span>Approve</span><span>Move forward</span></div>
        </div>
        <div className="auth-visual-footer"><span>Third Code Solutions Inc.</span><span>Private finance workspace</span></div>
      </section>

      <section className="auth-panel">
        <div className="auth-panel-inner">
          <div className="auth-mobile-brand"><span className="brand-mark">T</span><strong>TCSI Accounting</strong></div>
          <Link className="auth-back-link" href="/">← Back to TCSI home</Link>
          <div className="auth-heading">
            <span className="eyebrow">Secure workspace access</span>
            <h2>{title}</h2>
            <p>{mode === "signin" ? pilotPortal ? "Sign in with your assigned TCSI owner credentials. Accounting staff use the customer workspace." : "Sign in with your assigned TCSI workspace credentials." : mode === "update" ? "Choose a new password for your TCSI account." : "Enter your email and we’ll send a secure reset link."}</p>
          </div>

          {!configured && (
            <div className="auth-notice"><Sparkles aria-hidden="true" size={17} /><span>Demo shell ready · connect Supabase to enable sign in.</span></div>
          )}

          <form className="auth-form" onSubmit={submit}>
            {mode !== "update" && (
              <label className="field-label">Email address<input autoComplete="email" inputMode="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" required /></label>
            )}
            {mode !== "reset" && (
              <label className="field-label">{mode === "update" ? "New password" : "Password"}
                <span className="password-field"><input autoComplete={mode === "update" ? "new-password" : "current-password"} type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={mode === "update" ? "At least 12 characters" : "Your password"} minLength={mode === "update" ? 12 : 8} required /><button type="button" className="password-toggle" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((value) => !value)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></span>
              </label>
            )}
            {mode === "update" && (
              <label className="field-label">Confirm new password<input autoComplete="new-password" type={showPassword ? "text" : "password"} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Repeat the new password" minLength={12} required /></label>
            )}
            {mode === "signin" && <a className="form-link form-link--right" href="#reset" onClick={(event) => { event.preventDefault(); setMode("reset"); setError(""); }}>Forgot password?</a>}
            <button className="button button--primary button--full" type="submit" disabled={busy}>{busy ? "Working…" : submitLabel}<ArrowRight aria-hidden="true" size={17} /></button>
          </form>

          {error && <p className="form-message form-message--error" role="alert">{error}</p>}
          {message && <p className="form-message form-message--success" role="status"><Check aria-hidden="true" size={16} />{message}</p>}

          {mode !== "update" && (
            <div className="auth-switch">
              {mode === "signin" ? pilotPortal ? <>Accounting staff? <Link href="/web/login">Open the customer workspace</Link></> : <>Access is assigned by your administrator.</> : <>Already have access? <a href="#signin" onClick={(event) => { event.preventDefault(); setMode("signin"); setError(""); }}>Return to sign in</a></>}
            </div>
          )}
          <div className="auth-trust"><LockKeyhole aria-hidden="true" size={15} /><span>Protected workspace · access follows your assigned role</span></div>
        </div>
        <footer className="auth-footer"><span>© {new Date().getFullYear()} Third Code Solutions Inc.</span><a href="https://www.thirdcodesolutions.com" target="_blank" rel="noreferrer">thirdcodesolutions.com</a></footer>
      </section>
    </main>
  );
}
