"use client";

import { useState } from "react";
import Link from "next/link";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";
import { useAuthorization } from "@/lib/useAuthorization";

const TEXT_MAX = 200;
const STUDENT_ID_MAX = 64;
const STUDENT_ID = /^[A-Za-z0-9][A-Za-z0-9._/-]*$/;

const FIELDS = [
  { name: "student_name", label: "Student name" },
  { name: "student_id", label: "Student ID", hint: "Letters, digits and . _ / - only" },
  { name: "institution", label: "Institution" },
  { name: "degree", label: "Degree", placeholder: "Bachelor of Technology" },
  { name: "field_of_study", label: "Field of study", placeholder: "Computer Science and Engineering" },
  { name: "graduation_date", label: "Graduation date", type: "date" },
];

const EMPTY = {
  student_name: "",
  student_id: "",
  institution: process.env.NEXT_PUBLIC_INSTITUTION_NAME ?? "",
  degree: "",
  field_of_study: "",
  graduation_date: "",
};

// The backend compares against the UTC date, so the UI does too.
const todayUtc = () => new Date().toISOString().slice(0, 10);
const clean = (v) => v.trim().replace(/\s+/g, " ");

// Convenience checks only; the backend validates everything again.
function validate(values) {
  const errors = {};
  for (const { name } of FIELDS) {
    const v = clean(values[name]);
    if (!v) errors[name] = "Required";
    else if (name === "student_id") {
      if (v.length > STUDENT_ID_MAX || !STUDENT_ID.test(v))
        errors[name] = "Use letters, digits and . _ / - only (max 64)";
    } else if (name === "graduation_date") {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) errors[name] = "Enter a valid date";
      else if (v > todayUtc()) errors[name] = "Date cannot be in the future";
    } else if (v.length > TEXT_MAX) errors[name] = `At most ${TEXT_MAX} characters`;
  }
  return errors;
}

function submitMessage(err) {
  switch (err?.status) {
    case 0:
      return "Could not reach the server. Check whether the certificate was issued before trying again.";
    case 403:
      return "You no longer have permission to issue certificates.";
    case 409:
      return "A certificate ID conflict occurred. Nothing was issued; please try again.";
    case 422:
      return err.message;
    case 503:
      return "The certificate service is unavailable. Nothing was issued; please try again shortly.";
    default:
      return "Something went wrong. Nothing was confirmed as issued.";
  }
}

function Field({ field, value, error, onChange, max }) {
  const id = `f-${field.name}`;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {field.label}
      </label>
      <input
        id={id}
        name={field.name}
        type={field.type ?? "text"}
        value={value}
        onChange={onChange}
        placeholder={field.placeholder}
        max={field.type === "date" ? max : undefined}
        autoComplete="off"
        aria-invalid={error ? "true" : undefined}
        aria-describedby={error ? `${id}-err` : undefined}
        className={`mt-1 w-full rounded-md border px-3 py-2 text-ink focus:border-brand ${
          error ? "border-red-400" : "border-line"
        }`}
      />
      {error ? (
        <p id={`${id}-err`} className="mt-1 text-sm text-red-700">
          {error}
        </p>
      ) : (
        field.hint && <p className="mt-1 text-xs text-muted">{field.hint}</p>
      )}
    </div>
  );
}

function Summary({ values }) {
  return (
    <dl className="divide-y divide-line rounded-lg border border-line bg-white">
      {FIELDS.map((f) => (
        <div key={f.name} className="grid gap-1 px-5 py-3 sm:grid-cols-3">
          <dt className="text-sm text-muted">{f.label}</dt>
          <dd className="text-ink sm:col-span-2">{clean(values[f.name])}</dd>
        </div>
      ))}
    </dl>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable: the ID is still visible to copy by hand
    }
  }
  return (
    <button
      type="button"
      onClick={copy}
      className="rounded-md border border-line px-3 py-1 text-sm text-brand-dark hover:bg-brand-soft"
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function Issued({ result, onAnother }) {
  const { certificate: c, signature_metadata: m } = result;
  return (
    <div>
      <div className="rounded-lg border border-brand bg-brand-soft p-6">
        <h2 className="font-serif text-2xl font-semibold text-brand-dark">Certificate issued</h2>
        <p className="mt-2 text-sm text-muted">
          The certificate for {c.student_name} has been signed and saved.
        </p>
        <p className="mt-5 text-xs uppercase tracking-widest text-muted">Certificate ID</p>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <code className="break-all font-mono text-sm text-ink">{c.certificate_id}</code>
          <CopyButton text={c.certificate_id} />
        </div>
        <dl className="mt-5 grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted">Issue date</dt>
            <dd className="text-ink">{c.issue_date}</dd>
          </div>
          <div>
            <dt className="text-muted">Signature</dt>
            <dd className="text-ink">
              {m.algorithm}, key {m.key_id}
            </dd>
          </div>
        </dl>
      </div>
      <div className="mt-6 flex flex-wrap gap-4">
        <Link
          href={`/certificates/${c.certificate_id}`}
          className="rounded-md bg-brand px-5 py-2.5 font-medium text-white hover:bg-brand-dark"
        >
          View certificate
        </Link>
        <button
          type="button"
          onClick={onAnother}
          className="rounded-md border border-brand px-5 py-2.5 font-medium text-brand hover:bg-brand-soft"
        >
          Issue another
        </button>
      </div>
    </div>
  );
}

function IssueContent() {
  const { authFetch } = useAuth();
  const { loading, error: accessError, can, retry } = useAuthorization();
  const [step, setStep] = useState("edit"); // edit | review | done
  const [values, setValues] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [result, setResult] = useState(null);

  function onChange(e) {
    const { name, value } = e.target;
    setValues((v) => ({ ...v, [name]: value }));
    if (errors[name]) setErrors((er) => ({ ...er, [name]: undefined }));
  }

  function onReview(e) {
    e.preventDefault();
    const found = validate(values);
    setErrors(found);
    if (Object.keys(found).length === 0) {
      setSubmitError("");
      setStep("review");
    }
  }

  async function onIssue() {
    if (submitting) return; // never send twice
    setSubmitting(true);
    setSubmitError("");
    try {
      const body = Object.fromEntries(FIELDS.map((f) => [f.name, clean(values[f.name])]));
      const data = await authFetch("/certificates", { method: "POST", body });
      setResult(data);
      setStep("done");
    } catch (err) {
      setSubmitError(submitMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  function issueAnother() {
    setValues(EMPTY);
    setErrors({});
    setSubmitError("");
    setResult(null);
    setStep("edit");
  }

  return (
    <section className="mx-auto max-w-3xl px-6 py-12">
      <Link href="/dashboard" className="text-sm text-muted hover:text-brand-dark">
        &larr; Dashboard
      </Link>
      <h1 className="mt-3 font-serif text-3xl font-semibold text-brand-dark">Issue a certificate</h1>

      {loading && <p className="mt-8 text-muted">Loading&hellip;</p>}

      {accessError && (
        <div role="alert" className="mt-8 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <p>{accessError}</p>
          <button type="button" onClick={retry} className="mt-2 font-medium underline">
            Try again
          </button>
        </div>
      )}

      {!loading && !accessError && !can("certificate:issue") && (
        <div className="mt-8 rounded-lg border border-line bg-brand-soft p-6 text-sm text-muted">
          Your account is not authorised to issue certificates. Contact an
          administrator if you need this access.
        </div>
      )}

      {!loading && !accessError && can("certificate:issue") && (
        <div className="mt-8">
          {step === "edit" && (
            <form onSubmit={onReview} noValidate className="space-y-5">
              <p className="text-sm text-muted">
                The certificate ID and issue date are generated automatically.
              </p>
              {FIELDS.map((f) => (
                <Field
                  key={f.name}
                  field={f}
                  value={values[f.name]}
                  error={errors[f.name]}
                  onChange={onChange}
                  max={todayUtc()}
                />
              ))}
              <button
                type="submit"
                className="rounded-md bg-brand px-6 py-2.5 font-medium text-white hover:bg-brand-dark"
              >
                Review
              </button>
            </form>
          )}

          {step === "review" && (
            <div className="space-y-6">
              <p className="text-sm text-muted">
                Check the details. Once issued, a certificate is signed and cannot be edited.
              </p>
              <Summary values={values} />
              {submitError && (
                <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                  {submitError}
                </p>
              )}
              <div className="flex flex-wrap gap-4">
                <button
                  type="button"
                  onClick={onIssue}
                  disabled={submitting}
                  className="rounded-md bg-brand px-6 py-2.5 font-medium text-white hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? "Issuing\u2026" : "Issue and sign"}
                </button>
                <button
                  type="button"
                  onClick={() => setStep("edit")}
                  disabled={submitting}
                  className="rounded-md border border-line px-6 py-2.5 font-medium text-brand-dark hover:bg-brand-soft disabled:opacity-60"
                >
                  Edit details
                </button>
              </div>
            </div>
          )}

          {step === "done" && result && <Issued result={result} onAnother={issueAnother} />}
        </div>
      )}
    </section>
  );
}

export default function IssuePage() {
  return (
    <RequireAuth>
      <IssueContent />
    </RequireAuth>
  );
}