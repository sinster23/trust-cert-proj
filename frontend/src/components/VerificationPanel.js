// Renders the outcome of a public verification. Wording is fixed per outcome;
// the only server text shown is the backend's own message, as plain text.

const RESULT_VIEW = {
  VALID: {
    tone: "valid",
    title: "Valid certificate",
    text: "The certificate's digital signature is valid and the certificate is currently active in Credence's official records.",
    signature: "Successful",
    next: [
      "This confirms the certificate record held by Credence. It does not verify a PDF, scan or printed copy. To confirm that a copy matches this record, contact the issuing institution.",
    ],
  },
  INVALID: {
    tone: "bad",
    title: "Invalid certificate",
    text: "The digital signature could not be verified. The certificate data may have been modified or the signature may not be authentic.",
    signature: "Failed",
    next: ["Contact the issuing institution for clarification."],
  },
  REVOKED: {
    tone: "warn",
    title: "Revoked certificate",
    text: "The certificate's digital signature is valid, but the certificate has been revoked by the issuing authority. It is not currently valid.",
    signature: "Successful",
    next: ["Do not rely on this certificate. Contact the issuing institution for details."],
  },
  NOT_FOUND: {
    tone: "neutral",
    title: "Certificate not found",
    text: "No matching certificate was found in Credence's official records.",
    signature: "Not checked",
    next: [
      "Check that the Certificate ID was entered correctly.",
      "Make sure no characters are missing.",
      "If the ID is correct, contact the issuing institution.",
    ],
  },
  UNVERIFIABLE: {
    tone: "neutral",
    title: "Verification temporarily unavailable",
    text: "Credence could not complete verification at this time. This does not mean the certificate is invalid.",
    signature: "Not established",
    next: ["Please try again after a short while."],
  },
};

const ERROR_VIEW = {
  network: {
    title: "Connection problem",
    text: "Unable to connect to Credence. Please check your internet connection and try again.",
  },
  timeout: {
    title: "Verification is taking longer than expected",
    text: "The request timed out. Please try again.",
  },
  unavailable: {
    title: "Service temporarily unavailable",
    text: "Credence could not complete verification at this time. Please try again shortly.",
  },
  gateway: {
    title: "Temporary service error",
    text: "A temporary service error occurred. Please try again shortly.",
  },
  "rate-limit": {
    title: "Too many requests",
    text: "Please wait a moment before trying again.",
  },
  access: {
    title: "Service access error",
    text: "Verification is public, but the service reported an access problem. Please try again later.",
  },
  server: {
    title: "Something went wrong while verifying this certificate",
    text: "Credence ran into an internal problem. Please try again.",
  },
  request: {
    title: "Request could not be processed",
    text: "The verification request was not accepted. Please check the Certificate ID and try again.",
  },
  unexpected: {
    title: "Unexpected response",
    text: "Credence returned a response that could not be understood, so no verification result is shown.",
  },
};

const TONE = {
  valid: "border-brand bg-brand-soft text-brand-dark",
  warn: "border-amber-300 bg-amber-50 text-amber-900",
  bad: "border-red-300 bg-red-50 text-red-900",
  neutral: "border-line bg-white text-ink",
};

const LIFECYCLE_LABEL = { ACTIVE: "Active", REVOKED: "Revoked" };

function Heading({ compact, children }) {
  return (
    <h2
      className={`font-serif font-semibold ${
        compact ? "text-xl" : "text-2xl uppercase tracking-wide sm:text-3xl"
      }`}
    >
      {children}
    </h2>
  );
}

function Retry({ onRetry }) {
  return (
    <button
      type="button"
      onClick={onRetry}
      className="mt-5 rounded-md border border-current px-4 py-2 text-sm font-medium"
    >
      Try again
    </button>
  );
}

export default function VerificationPanel({ outcome, certificateId, onRetry, compact = false }) {
  const pad = compact ? "p-5" : "p-6 sm:p-8";

  if (outcome.type === "result") {
    const { result } = outcome;
    const view = RESULT_VIEW[result.status];
    return (
      <div role="status" className={`rounded-lg border ${pad} ${TONE[view.tone]}`}>
        <Heading compact={compact}>{view.title}</Heading>
        <p className={`mt-3 leading-relaxed ${compact ? "text-sm" : ""}`}>{view.text}</p>

        <dl className="mt-6 grid gap-x-8 gap-y-4 text-sm sm:grid-cols-2">
          {!compact && (
            <div className="sm:col-span-2">
              <dt className="opacity-70">Certificate ID</dt>
              <dd className="mt-0.5 break-all font-mono text-xs">{result.certificate_id}</dd>
            </div>
          )}
          <div>
            <dt className="opacity-70">Signature verification</dt>
            <dd className="mt-0.5 font-medium">{view.signature}</dd>
          </div>
          {result.certificate_status && (
            <div>
              <dt className="opacity-70">Certificate status</dt>
              <dd className="mt-0.5 font-medium">{LIFECYCLE_LABEL[result.certificate_status]}</dd>
            </div>
          )}
          {!compact && (
            <div className="sm:col-span-2">
              <dt className="opacity-70">Message from Credence</dt>
              <dd className="mt-0.5">{result.message}</dd>
            </div>
          )}
        </dl>

        {!compact && (
          <div className="mt-6 border-t border-current/20 pt-5 text-sm leading-relaxed">
            <p className="font-medium">What to do next</p>
            {view.next.length === 1 ? (
              <p className="mt-1">{view.next[0]}</p>
            ) : (
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {view.next.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {result.status === "UNVERIFIABLE" && onRetry && <Retry onRetry={onRetry} />}
      </div>
    );
  }

  if (outcome.type === "invalid-id") {
    return (
      <div role="alert" className={`rounded-lg border ${pad} ${TONE.neutral}`}>
        <Heading compact={compact}>Invalid Certificate ID</Heading>
        <p className={`mt-3 ${compact ? "text-sm" : ""}`}>
          Certificate IDs start with CERT- followed by 32 hexadecimal characters.
        </p>
      </div>
    );
  }

  const view = ERROR_VIEW[outcome.reason] ?? ERROR_VIEW.unexpected;
  const wait =
    outcome.reason === "rate-limit" && outcome.retryAfter
      ? ` Try again in about ${outcome.retryAfter} second${outcome.retryAfter === 1 ? "" : "s"}.`
      : "";
  return (
    <div role="alert" className={`rounded-lg border ${pad} ${TONE.neutral}`}>
      <Heading compact={compact}>{view.title}</Heading>
      <p className={`mt-3 leading-relaxed ${compact ? "text-sm" : ""}`}>
        {view.text}
        {wait}
      </p>
      <p className={`mt-2 text-muted ${compact ? "text-xs" : "text-sm"}`}>
        No verification result was established. This does not mean the certificate is invalid.
      </p>
      {!compact && certificateId && (
        <p className="mt-4 break-all font-mono text-xs text-muted">{certificateId}</p>
      )}
      {onRetry && <Retry onRetry={onRetry} />}
    </div>
  );
}