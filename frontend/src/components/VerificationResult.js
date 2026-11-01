"use client";

import { useCallback, useEffect, useState } from "react";
import VerificationPanel from "@/components/VerificationPanel";
import VerificationReport from "@/components/VerificationReport";
import { verifyCertificate } from "@/lib/verify";

const LOADING = { loading: true, outcome: null };

export default function VerificationResult({ id }) {
  const [state, setState] = useState(LOADING);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    verifyCertificate(id, { signal: controller.signal }).then((outcome) => {
      if (controller.signal.aborted || outcome.type === "aborted") return;
      setState({ loading: false, outcome });
    });
    return () => controller.abort(); // leaving the page cancels the request
  }, [id, attempt]);

  const retry = useCallback(() => {
    setState(LOADING);
    setAttempt((n) => n + 1);
  }, []);

  return (
    <div aria-live="polite">
      {state.loading && (
        <div className="flex items-center gap-3 text-muted">
          <span
            className="h-5 w-5 animate-spin rounded-full border-2 border-line border-t-brand"
            aria-hidden="true"
          />
          <span>Verifying certificate...</span>
        </div>
      )}
      {!state.loading && state.outcome.type === "result" && (
        <VerificationReport result={state.outcome.result} onRetry={retry} />
      )}
      {!state.loading && state.outcome.type !== "result" && (
        <VerificationPanel outcome={state.outcome} certificateId={id} onRetry={retry} />
      )}
    </div>
  );
}