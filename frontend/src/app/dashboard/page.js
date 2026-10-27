"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";
import { useAuthorization } from "@/lib/useAuthorization";
import { permissionLabel, roleLabel } from "@/lib/access";

const CERTIFICATE_ID = /^CERT-[0-9a-f]{32}$/;

function Card({ title, children }) {
  return (
    <div className="rounded-lg border border-line bg-white p-6">
      <h2 className="font-serif text-xl font-semibold text-brand-dark">{title}</h2>
      <div className="mt-3 text-sm leading-relaxed text-muted">{children}</div>
    </div>
  );
}

function LookupCard() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  function onSubmit(e) {
    e.preventDefault();
    const id = value.trim();
    if (!CERTIFICATE_ID.test(id)) {
      setError("Enter a valid certificate ID (CERT- followed by 32 characters).");
      return;
    }
    setError("");
    router.push(`/certificates/${id}`);
  }

  return (
    <Card title="Look up a certificate">
      <form onSubmit={onSubmit} className="space-y-3">
        <label htmlFor="cert-id" className="block text-ink">
          Certificate ID
        </label>
        <input
          id="cert-id"
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="CERT-..."
          autoComplete="off"
          spellCheck={false}
          className="w-full rounded-md border border-line px-3 py-2 font-mono text-sm text-ink placeholder:text-muted/60 focus:border-brand"
        />
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
        <button
          type="submit"
          className="rounded-md border border-brand px-4 py-2 font-medium text-brand hover:bg-brand-soft"
        >
          View certificate
        </button>
      </form>
    </Card>
  );
}

function DashboardContent() {
  const { user } = useAuth();
  const { loading, error, role, permissions, can, retry } = useAuthorization();

  return (
    <section className="mx-auto max-w-6xl px-6 py-12">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
        <div>
          <h1 className="font-serif text-3xl font-semibold text-brand-dark">Dashboard</h1>
          <p className="mt-1 text-sm text-muted">{user.email}</p>
        </div>
        {!loading && !error && (
          <span className="rounded-full border border-brand px-4 py-1 text-sm font-medium text-brand">
            {roleLabel(role)}
          </span>
        )}
      </div>

      {loading && <p className="mt-8 text-muted">Loading&hellip;</p>}

      {error && (
        <div role="alert" className="mt-8 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <p>{error}</p>
          <button type="button" onClick={retry} className="mt-2 font-medium underline">
            Try again
          </button>
        </div>
      )}

      {!loading && !error && (
        <div className="mt-8 grid gap-6 md:grid-cols-2">
          {can("certificate:issue") ? (
            <Card title="Issue a certificate">
              <p>
                Enter a graduate&apos;s details. The certificate ID is generated
                for you and the certificate is digitally signed.
              </p>
              <Link
                href="/dashboard/issue"
                className="mt-4 inline-block rounded-md bg-brand px-4 py-2 font-medium text-white hover:bg-brand-dark"
              >
                New certificate
              </Link>
            </Card>
          ) : (
            <Card title="Certificates">
              <p>
                Your account has view-only access. Certificates are issued by
                authorised staff.
              </p>
            </Card>
          )}

          <LookupCard />

          <div className="md:col-span-2">
            <Card title="Your access">
              {permissions.length === 0 ? (
                <p>No permissions are assigned to this account.</p>
              ) : (
                <ul className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
                  {permissions.map((p) => (
                    <li key={p} className="flex items-start gap-2">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
                      <span>{permissionLabel(p)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </div>
      )}
    </section>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardContent />
    </RequireAuth>
  );
}