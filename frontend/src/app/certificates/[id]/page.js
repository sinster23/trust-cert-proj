"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";

// "2025-06-15" -> "15 June 2025" (no timezone shifting)
function formatDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

function loadError(err) {
  switch (err?.status) {
    case 404:
      return { kind: "notfound", message: "No certificate was found with this ID." };
    case 422:
      return { kind: "notfound", message: "This is not a valid certificate ID." };
    case 0:
      return { kind: "error", message: "Could not reach the server. Please try again." };
    case 503:
      return { kind: "error", message: "The certificate service is unavailable. Please try again shortly." };
    default:
      return { kind: "error", message: "The certificate could not be loaded." };
  }
}

function Message({ error, onRetry }) {
  return (
    <div
      role="alert"
      className={`rounded-lg border p-6 text-sm ${
        error.kind === "notfound"
          ? "border-line bg-brand-soft text-muted"
          : "border-red-200 bg-red-50 text-red-800"
      }`}
    >
      <p>{error.message}</p>
      {error.kind === "error" && (
        <button type="button" onClick={onRetry} className="mt-2 font-medium underline">
          Try again
        </button>
      )}
    </div>
  );
}

function CertificateSheet({ certificate: c }) {
  return (
    <article className="border-4 border-double border-brand bg-white p-3 sm:p-4">
      <div className="border border-line px-6 py-10 text-center sm:px-14 sm:py-14">
        <p className="text-xs uppercase tracking-[0.3em] text-brand">{c.institution}</p>
        <h1 className="mt-4 font-serif text-3xl font-semibold text-brand-dark sm:text-4xl">
          Certificate of Graduation
        </h1>
        <div className="mx-auto mt-6 h-px w-24 bg-brand" />

        <p className="mt-8 text-muted">This is to certify that</p>
        <p className="mt-3 font-serif text-3xl text-ink sm:text-4xl">{c.student_name}</p>
        <p className="mt-2 text-sm text-muted">Student ID {c.student_id}</p>

        <p className="mt-8 text-muted">has been awarded the degree of</p>
        <p className="mt-3 font-serif text-2xl text-brand-dark">{c.degree}</p>
        <p className="mt-2 text-ink">in {c.field_of_study}</p>

        <p className="mt-8 text-muted">Date of graduation</p>
        <p className="mt-1 text-ink">{formatDate(c.graduation_date)}</p>

        <dl className="mt-12 grid gap-4 border-t border-line pt-6 text-left text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-widest text-muted">Issued on</dt>
            <dd className="mt-1 text-ink">{formatDate(c.issue_date)}</dd>
          </div>
          <div className="sm:text-right">
            <dt className="text-xs uppercase tracking-widest text-muted">Certificate ID</dt>
            <dd className="mt-1 break-all font-mono text-xs text-ink">{c.certificate_id}</dd>
          </div>
        </dl>
      </div>
    </article>
  );
}

function SignaturePanel({ meta }) {
  return (
    <div className="mt-8 rounded-lg border border-line bg-brand-soft p-6">
      <h2 className="font-serif text-xl font-semibold text-brand-dark">Digital signature</h2>
      <dl className="mt-4 grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted">Algorithm</dt>
          <dd className="text-ink">{meta.algorithm}</dd>
        </div>
        <div>
          <dt className="text-muted">Key ID</dt>
          <dd className="break-all text-ink">{meta.key_id}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-muted">Signature</dt>
          <dd className="mt-1 break-all font-mono text-xs text-ink">{meta.signature}</dd>
        </div>
      </dl>
      <p className="mt-4 text-xs leading-relaxed text-muted">
        This page shows the stored certificate record and its signature.
        Automated signature verification is not yet available here.
      </p>
    </div>
  );
}

function CertificateContent() {
  const { id } = useParams();
  const { authFetch } = useAuth();
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await authFetch(`/certificates/${encodeURIComponent(id)}`);
        if (!cancelled) setState({ loading: false, data, error: null });
      } catch (err) {
        if (!cancelled && err?.status !== 401)
          setState({ loading: false, data: null, error: loadError(err) });
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id, authFetch, attempt]);

  const retry = useCallback(() => {
    setState({ loading: true, data: null, error: null });
    setAttempt((n) => n + 1);
  }, []);

  return (
    <section className="mx-auto max-w-3xl px-6 py-12">
      <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-4">
        <Link href="/dashboard" className="text-sm text-muted hover:text-brand-dark">
          &larr; Dashboard
        </Link>
        {state.data && (
          <button
            type="button"
            onClick={() => window.print()}
            className="rounded-md border border-brand px-4 py-2 text-sm font-medium text-brand hover:bg-brand-soft"
          >
            Print
          </button>
        )}
      </div>

      {state.loading && <p className="text-muted">Loading&hellip;</p>}
      {state.error && <Message error={state.error} onRetry={retry} />}
      {state.data && (
        <>
          <CertificateSheet certificate={state.data.certificate} />
          <SignaturePanel meta={state.data.signature_metadata} />
        </>
      )}
    </section>
  );
}

export default function CertificatePage() {
  return (
    <RequireAuth>
      <CertificateContent />
    </RequireAuth>
  );
}