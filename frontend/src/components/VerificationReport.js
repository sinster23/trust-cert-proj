"use client";

import { useState } from "react";
import { formatIsoDate } from "@/lib/format";

// Part 1: Authenticity. Part 2: Document comparison (official record + checklist,
// or a clear "details withheld" statement). Details come from lib/verify.js, which
// has already checked they are exactly the seven public fields with a masked ID.

const STATUS_VIEW = {
  VALID: {
    tone: "valid", eyebrow: "Authenticity", title: "Valid certificate",
    text: "The digital signature is valid and the certificate is currently active in Credence's official records.",
    signature: "Successful", next: [],
  },
  REVOKED: {
    tone: "warn", eyebrow: "Revoked certificate", title: "Not currently valid",
    text: "The digital signature is valid, but the issuing authority has revoked this certificate. Do not rely on it.",
    signature: "Successful", next: ["Contact the issuing institution for details."],
  },
  INVALID: {
    tone: "bad", eyebrow: "Authenticity", title: "Invalid certificate",
    text: "The digital signature could not be verified. The certificate data may have been modified, or the signature may not be authentic.",
    signature: "Failed",
    next: ["Do not rely on this certificate.", "Contact the issuing institution for clarification."],
  },
  NOT_FOUND: {
    tone: "neutral", eyebrow: "Authenticity", title: "Certificate not found",
    text: "No matching certificate was found in Credence's official records.",
    signature: "Not checked",
    next: [
      "Check that the Certificate ID was entered correctly and no characters are missing.",
      "If the ID is correct, contact the issuing institution.",
    ],
  },
  UNVERIFIABLE: {
    tone: "neutral", eyebrow: "Authenticity", title: "Verification temporarily unavailable",
    text: "Credence could not complete verification at this time. This does not mean the certificate is invalid.",
    signature: "Not established", next: ["Please try again after a short while."],
  },
};

const BANNER_TONE = {
  valid: "border-brand bg-brand-soft text-brand-dark",
  warn: "border-amber-400 bg-amber-50 text-amber-900",
  bad: "border-red-300 bg-red-50 text-red-900",
  neutral: "border-line bg-white text-ink",
};

// Green for valid, never for revoked.
const CARD_TONE = { VALID: "border-brand", REVOKED: "border-amber-400" };

const LIFECYCLE_LABEL = { ACTIVE: "Active", REVOKED: "Revoked" };

const COMPARE_ITEMS = [
  ["name", "The name on your copy is exactly the name above."],
  ["student_id", "The visible characters of the student ID match."],
  ["degree", "The degree matches."],
  ["field", "The field of study matches."],
  ["institution", "The institution matches."],
  ["graduation", "The date of graduation matches."],
  ["issue", "The issue date matches."],
  ["cert_id", "The Certificate ID on your copy matches the one on this page."],
];

function SectionHeading({ children }) {
  return <h2 className="font-serif text-xl font-semibold text-brand-dark">{children}</h2>;
}

function RecordRow({ label, value, wide = false, mono = false }) {
  return (
    <div className={wide ? "sm:col-span-2" : undefined}>
      <dt className="text-xs uppercase tracking-widest text-muted">{label}</dt>
      <dd className={`mt-1 text-ink ${mono ? "break-all font-mono text-sm" : "font-serif text-lg"}`}>
        {value}
      </dd>
    </div>
  );
}

function OfficialRecord({ result }) {
  const d = result.details;
  return (
    <article
      aria-label="Official record"
      className={`border-4 border-double bg-white p-2 sm:p-3 ${CARD_TONE[result.status]}`}
    >
      <div className="border border-line px-5 py-6 sm:px-8 sm:py-8">
        <p className="text-xs uppercase tracking-[0.25em] text-brand">{d.institution}</p>
        <h3 className="mt-2 font-serif text-2xl font-semibold text-brand-dark">Official record</h3>
        <div className="mt-3 h-px w-16 bg-brand" />
        <dl className="mt-6 grid gap-x-8 gap-y-5 sm:grid-cols-2">
          <RecordRow label="Name" value={d.student_name} wide />
          <RecordRow label="Student ID" value={d.student_id} mono />
          <RecordRow label="Certificate ID" value={result.certificate_id} mono wide />
          <RecordRow label="Degree" value={d.degree} />
          <RecordRow label="Field of study" value={d.field_of_study} />
          <RecordRow label="Date of graduation" value={formatIsoDate(d.graduation_date)} />
          <RecordRow label="Issued on" value={formatIsoDate(d.issue_date)} />
        </dl>
        <p className="mt-6 border-t border-line pt-4 text-xs leading-relaxed text-muted">
          The student ID is partly hidden to protect the graduate&apos;s privacy. Compare the
          characters that are shown.
        </p>
      </div>
    </article>
  );
}

function CompareChecklist({ revoked }) {
  return (
    <div className="mt-8">
      <SectionHeading>Compare with your copy</SectionHeading>
      <p className="mt-2 text-sm leading-relaxed text-muted">
        Check the document you were given against the official record above, item by item.
      </p>
      <ul className="mt-4 space-y-2">
        {COMPARE_ITEMS.map(([key, label]) => (
          <li key={key}>
            <label className="flex items-start gap-3 text-sm text-ink">
              <input type="checkbox" className="mt-0.5 h-4 w-4 accent-brand" />
              <span>{label}</span>
            </label>
          </li>
        ))}
      </ul>
      <p className="mt-4 rounded-md border border-line bg-white p-4 text-sm font-medium leading-relaxed text-ink">
        If any item does not match, the document is not genuine.
        {revoked
          ? " Even if every item matches, this certificate has been revoked and should not be relied on."
          : ""}
      </p>
    </div>
  );
}

function DetailsWithheld({ revoked }) {
  return (
    <div className="rounded-lg border border-line bg-white p-5 text-sm leading-relaxed text-ink">
      <p className="font-medium">Official certificate details are withheld.</p>
      <p className="mt-2 text-muted">
        The result above confirms the cryptographic status of this Credence record
        {revoked ? " (authentic, but revoked)" : " (authentic and active)"}. The issuing
        institution has not yet approved showing the certificate&apos;s contents publicly, so the
        document you were given{" "}
        <strong className="font-medium text-ink">
          cannot be compared with the official record through this page
        </strong>
        . A status-only result is not a check that the document in your hands matches the record.
      </p>
    </div>
  );
}

function Notices() {
  return (
    <div className="mt-8 rounded-lg border border-line bg-white p-5 text-sm leading-relaxed text-muted">
      <p className="font-medium text-ink">Please note</p>
      <ul className="mt-2 list-disc space-y-1.5 pl-5">
        <li>
          This page verifies the certificate record held by Credence. It does not verify a PDF,
          scan or printed copy.
        </li>
        <li>
          It does not confirm that the person presenting the certificate is the named graduate.
          Match the name and student ID against a photo ID.
        </li>
      </ul>
    </div>
  );
}

function ShareLink({ certificateId }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/verify/${certificateId}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable
    }
  }
  return (
    <div className="no-print mt-8 flex flex-wrap items-center gap-3 text-sm text-muted">
      <span>Share this result</span>
      <button
        type="button"
        onClick={copy}
        className="rounded-md border border-line bg-white px-3 py-1 text-brand-dark hover:bg-brand-soft"
      >
        {copied ? "Copied" : "Copy link"}
      </button>
    </div>
  );
}

export default function VerificationReport({ result, onRetry }) {
  const view = STATUS_VIEW[result.status];
  const hasRecordSection = result.status === "VALID" || result.status === "REVOKED";
  const revoked = result.status === "REVOKED";

  return (
    <div>
      <section aria-labelledby="authenticity-heading">
        <h2 id="authenticity-heading" className="sr-only">Authenticity</h2>
        <div role="status" className={`rounded-lg border-2 p-6 sm:p-8 ${BANNER_TONE[view.tone]}`}>
          <p className="text-xs font-medium uppercase tracking-widest opacity-80">{view.eyebrow}</p>
          <p className="mt-2 font-serif text-3xl font-semibold uppercase tracking-wide sm:text-4xl">
            {view.title}
          </p>
          <p className="mt-3 max-w-2xl leading-relaxed">{view.text}</p>
        </div>

        <dl className="mt-6 grid gap-x-8 gap-y-4 rounded-lg border border-line bg-white p-5 text-sm sm:grid-cols-2">
          <div className="sm:col-span-2">
            <dt className="text-muted">Certificate ID</dt>
            <dd className="mt-0.5 break-all font-mono text-xs text-ink">{result.certificate_id}</dd>
          </div>
          <div>
            <dt className="text-muted">Signature verification</dt>
            <dd className="mt-0.5 font-medium text-ink">{view.signature}</dd>
          </div>
          {result.certificate_status && (
            <div>
              <dt className="text-muted">Certificate status</dt>
              <dd className="mt-0.5 font-medium text-ink">
                {LIFECYCLE_LABEL[result.certificate_status]}
              </dd>
            </div>
          )}
          <div className="sm:col-span-2">
            <dt className="text-muted">Message from Credence</dt>
            <dd className="mt-0.5 text-ink">{result.message}</dd>
          </div>
        </dl>

        {view.next.length > 0 && (
          <div className="mt-6 text-sm leading-relaxed text-ink">
            <p className="font-medium">What to do next</p>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {view.next.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        )}

        {result.status === "UNVERIFIABLE" && onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="no-print mt-5 rounded-md border border-brand px-4 py-2 text-sm font-medium text-brand-dark hover:bg-brand-soft"
          >
            Try again
          </button>
        )}
      </section>

      {hasRecordSection && (
        <section aria-labelledby="comparison-heading" className="mt-12">
          <h2 id="comparison-heading" className="font-serif text-2xl font-semibold text-brand-dark">
            Document comparison
          </h2>
          <div className="mt-4">
            {result.details_available ? (
              <>
                <OfficialRecord result={result} />
                <CompareChecklist revoked={revoked} />
              </>
            ) : (
              <DetailsWithheld revoked={revoked} />
            )}
          </div>
          <Notices />
        </section>
      )}

      <ShareLink certificateId={result.certificate_id} />
    </div>
  );
}