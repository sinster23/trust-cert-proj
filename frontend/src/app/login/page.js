"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Script from "next/script";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

function messageFor(err) {
  if (!(err instanceof ApiError)) return "Sign-in failed. Please try again.";
  if (err.status === 0) return "Could not reach the server. Please try again.";
  if (err.status === 401)
    return "Sign-in failed. Use your institutional Google account.";
  if (err.status === 403) return "This account is not available.";
  if (err.status === 503) return "Sign-in is temporarily unavailable. Please try again later.";
  return "Sign-in failed. Please try again.";
}

export default function LoginPage() {
  const router = useRouter();
  const { status, login } = useAuth();
  const buttonRef = useRef(null);
  const [gsiReady, setGsiReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Already signed in: go straight to the dashboard.
  useEffect(() => {
    if (status === "authenticated") router.replace("/dashboard");
  }, [status, router]);

  const handleCredential = useCallback(
    async (response) => {
      setError("");
      setBusy(true);
      try {
        await login(response.credential);
        router.replace("/dashboard");
      } catch (err) {
        setError(messageFor(err));
        setBusy(false);
      }
    },
    [login, router],
  );

  // Render Google's official button once the Google script has loaded.
  useEffect(() => {
    if (!gsiReady || !CLIENT_ID || !buttonRef.current) return;
    window.google.accounts.id.initialize({
      client_id: CLIENT_ID,
      callback: handleCredential,
    });
    window.google.accounts.id.renderButton(buttonRef.current, {
      theme: "outline",
      size: "large",
      shape: "rectangular",
      text: "signin_with",
      width: 300,
    });
  }, [gsiReady, handleCredential]);

  return (
    <section className="bg-brand-soft">
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onReady={() => setGsiReady(true)}
      />
      <div className="mx-auto flex max-w-6xl justify-center px-6 py-16 sm:py-24">
        <div className="w-full max-w-md rounded-lg border border-line bg-white p-8 shadow-sm">
          <h1 className="font-serif text-3xl font-semibold text-brand-dark">Sign in</h1>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            Use your institutional Google account. Accounts outside the
            institute&apos;s domain are not accepted.
          </p>

          <div className="mt-8 flex min-h-[44px] justify-center">
            {CLIENT_ID ? (
              <div ref={buttonRef} />
            ) : (
              <p className="text-sm text-red-700">
                Google sign-in is not configured. Set NEXT_PUBLIC_GOOGLE_CLIENT_ID.
              </p>
            )}
          </div>

          {busy && <p className="mt-6 text-center text-sm text-muted">Signing in&hellip;</p>}
          {error && (
            <p
              role="alert"
              className="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            >
              {error}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}