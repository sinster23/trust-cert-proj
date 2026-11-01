"use client";

import { useCallback, useEffect, useState } from "react";
import VerificationPanel from "@/components/VerificationPanel";
import { verifyCertificate } from "@/lib/verify";

// Runs the public verification for a certificate and shows the result,
// plus a shareable link anyone can use without signing in.
export default function VerificationSection({ certificateId }) {
  const [state, setState] = useState({ loading: true, outcome: null });
  const [attempt, setAttempt] = useState(0);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    verifyCertificate(certificateId).then((outcome) => {
      if (!cancelled) setState({ loading: false, outcome });
    });
    return () => {
      cancelled = true;
    };
  }, [certificateId, attempt]);

  const retry = useCallback(() => {
    setState({ loading: true, outcome: null });
    setAttempt((n) => n + 1);
  }, []);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/verify/${certificateId}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable
    }
  }

  return (
    <div className="no-print mt-8">
      <h2 className="mb-3 font-serif text-xl font-semibold text-brand-dark">Verification</h2>
      {state.loading ? (
        <p className="text-sm text-muted">Checking signature&hellip;</p>
      ) : (
        <VerificationPanel outcome={state.outcome} onRetry={retry} compact />
      )}
      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-muted">
          <span className="break-all font-mono text-xs text-ink">/verify/{certificateId}</span>
        <button
          type="button"
          onClick={copyLink}
          className="rounded-md border border-line px-3 py-1 text-brand-dark hover:bg-brand-soft"
        >
          {copied ? "Copied" : "Copy link"}
        </button>
      </div>
    </div>
  );
}