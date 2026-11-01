"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";
import { useAuthorization } from "@/lib/useAuthorization";
import { roleLabel } from "@/lib/access";

const PAGE = 25;
const FILTERS = [
  { value: "", label: "All" },
  { value: "STUDENT", label: "Students" },
  { value: "ISSUER", label: "Issuers" },
  { value: "ADMIN", label: "Administrators" },
];

function loadMessage(err) {
  if (err?.status === 403) return "You are not allowed to view users.";
  if (err?.status === 0) return "Could not reach the server. Please try again.";
  return "The user list could not be loaded. Please try again.";
}

function changeMessage(err) {
  switch (err?.status) {
    case 0:
      return "Could not reach the server. The change was not confirmed; refresh the list to check.";
    case 403:
      return err.message === "Forbidden" ? "You are not allowed to make this change." : err.message;
    case 404:
      return "That user no longer exists.";
    case 409:
      return err.message;
    case 503:
      return "The service is unavailable. No change was made; please try again shortly.";
    default:
      return "The change could not be completed.";
  }
}

function RoleBadge({ role }) {
  const style =
    role === "ISSUER"
      ? "bg-brand text-white border-brand"
      : role === "ADMIN"
        ? "border-brand-dark text-brand-dark"
        : "border-line text-muted";
  return (
    <span className={`inline-block rounded-full border px-3 py-0.5 text-xs font-medium ${style}`}>
      {roleLabel(role)}
    </span>
  );
}

// Only STUDENT <-> ISSUER changes are offered here. Admin changes are deliberately not in the UI.
function actionFor(u, selfId, canManage) {
  if (!canManage || u.id === selfId) return null;
  if (u.role === "STUDENT" && u.is_active) return { target: "ISSUER", label: "Make issuer" };
  if (u.role === "ISSUER") return { target: "STUDENT", label: "Remove issuer" };
  return null;
}

function UserRow({ u, action, pending, busy, onAsk, onConfirm, onCancel }) {
  const confirming = pending && pending.id === u.id;
  return (
    <tr className="border-t border-line">
      <td className="px-4 py-3 text-ink">{u.email}</td>
      <td className="px-4 py-3">
        <RoleBadge role={u.role} />
      </td>
      <td className="px-4 py-3 text-sm text-muted">{u.is_active ? "Active" : "Inactive"}</td>
      <td className="px-4 py-3 text-right">
        {action && !confirming && (
          <button
            type="button"
            onClick={() => onAsk(u, action)}
            disabled={busy}
            className="rounded-md border border-brand px-3 py-1.5 text-sm font-medium text-brand hover:bg-brand-soft disabled:opacity-60"
          >
            {action.label}
          </button>
        )}
        {action && confirming && (
          <span className="inline-flex items-center gap-2 text-sm">
            <span className="text-muted">{action.label}?</span>
            <button
              type="button"
              onClick={() => onConfirm(u, action)}
              disabled={busy}
              className="rounded-md bg-brand px-3 py-1.5 font-medium text-white hover:bg-brand-dark disabled:opacity-60"
            >
              {busy ? "Saving\u2026" : "Confirm"}
            </button>
            <button
              type="button"
              onClick={onCancel}
              disabled={busy}
              className="rounded-md border border-line px-3 py-1.5 text-brand-dark hover:bg-brand-soft disabled:opacity-60"
            >
              Cancel
            </button>
          </span>
        )}
      </td>
    </tr>
  );
}

function UsersTable({ canManage }) {
  const { user: me, authFetch } = useAuth();
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(0);
  const [reload, setReload] = useState(0);
  const [state, setState] = useState({ loading: true, error: "", users: [], hasNext: false });
  const [pending, setPending] = useState(null); // { id }
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null); // { type, text }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const params = new URLSearchParams({
        skip: String(page * PAGE),
        limit: String(PAGE + 1), // one extra row tells us whether a next page exists
      });
      if (filter) params.set("role", filter);
      try {
        const data = await authFetch(`/authorization/users?${params}`);
        if (!cancelled)
          setState({
            loading: false,
            error: "",
            users: data.users.slice(0, PAGE),
            hasNext: data.users.length > PAGE,
          });
      } catch (err) {
        if (!cancelled && err?.status !== 401)
          setState({ loading: false, error: loadMessage(err), users: [], hasNext: false });
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [authFetch, filter, page, reload]);

  function startLoading() {
    setState((s) => ({ ...s, loading: true, error: "" }));
    setPending(null);
  }

  function changeFilter(value) {
    if (value === filter) return;
    startLoading();
    setNotice(null);
    setFilter(value);
    setPage(0);
  }

  function goToPage(next) {
    startLoading();
    setPage(next);
  }

  async function confirm(u, action) {
    if (busy) return;
    setBusy(true);
    setNotice(null);
    try {
      const updated = await authFetch(`/authorization/users/${u.id}/role`, {
        method: "PUT",
        body: { role: action.target },
      });
      setState((s) => ({
        ...s,
        users: s.users
          .map((x) => (x.id === updated.id ? updated : x))
          .filter((x) => !filter || x.role === filter),
      }));
      setNotice({
        type: "success",
        text: `${updated.email} is now ${updated.role === "ISSUER" ? "an issuer" : "a student"}.`,
      });
      setPending(null);
    } catch (err) {
      if (err?.status !== 401) {
        setNotice({ type: "error", text: changeMessage(err) });
        setPending(null);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-8">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by role">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => changeFilter(f.value)}
            aria-pressed={filter === f.value}
            className={`rounded-full border px-4 py-1.5 text-sm ${
              filter === f.value
                ? "border-brand bg-brand text-white"
                : "border-line text-brand-dark hover:bg-brand-soft"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {notice && (
        <p
          role={notice.type === "error" ? "alert" : "status"}
          className={`mt-6 rounded-md border px-4 py-3 text-sm ${
            notice.type === "error"
              ? "border-red-200 bg-red-50 text-red-800"
              : "border-brand bg-brand-soft text-brand-dark"
          }`}
        >
          {notice.text}
        </p>
      )}

      {state.error && (
        <div role="alert" className="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <p>{state.error}</p>
          <button
            type="button"
            onClick={() => {
              startLoading();
              setReload((n) => n + 1);
            }}
            className="mt-2 font-medium underline"
          >
            Try again
          </button>
        </div>
      )}

      {state.loading && <p className="mt-6 text-muted">Loading&hellip;</p>}

      {!state.loading && !state.error && (
        <>
          <div className="mt-6 overflow-x-auto rounded-lg border border-line bg-white">
            <table className="w-full min-w-[36rem] text-left">
              <thead className="bg-brand-soft text-xs uppercase tracking-widest text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Email</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {state.users.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-sm text-muted">
                      No users found.
                    </td>
                  </tr>
                ) : (
                  state.users.map((u) => (
                    <UserRow
                      key={u.id}
                      u={u}
                      action={actionFor(u, me?.id, canManage)}
                      pending={pending}
                      busy={busy}
                      onAsk={(row) => setPending({ id: row.id })}
                      onConfirm={confirm}
                      onCancel={() => setPending(null)}
                    />
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex items-center justify-between text-sm">
            <button
              type="button"
              onClick={() => goToPage(page - 1)}
              disabled={page === 0}
              className="rounded-md border border-line px-4 py-2 text-brand-dark hover:bg-brand-soft disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-muted">Page {page + 1}</span>
            <button
              type="button"
              onClick={() => goToPage(page + 1)}
              disabled={!state.hasNext}
              className="rounded-md border border-line px-4 py-2 text-brand-dark hover:bg-brand-soft disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function AdminUsersContent() {
  const { loading, error, can, retry } = useAuthorization();

  return (
    <section className="mx-auto max-w-5xl px-6 py-12">
      <Link href="/dashboard" className="text-sm text-muted hover:text-brand-dark">
        &larr; Dashboard
      </Link>
      <h1 className="mt-3 font-serif text-3xl font-semibold text-brand-dark">Manage issuers</h1>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
        Grant or remove issuer access. Issuers can issue certificates;
        administrators manage access but cannot issue certificates themselves.
        Users appear here after their first sign-in.
      </p>

      {loading && <p className="mt-8 text-muted">Loading&hellip;</p>}

      {error && (
        <div role="alert" className="mt-8 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <p>{error}</p>
          <button type="button" onClick={retry} className="mt-2 font-medium underline">
            Try again
          </button>
        </div>
      )}

      {!loading && !error && !can("user:list") && (
        <div className="mt-8 rounded-lg border border-line bg-brand-soft p-6 text-sm text-muted">
          Your account is not authorised to manage users.
        </div>
      )}

      {!loading && !error && can("user:list") && <UsersTable canManage={can("issuer:manage")} />}
    </section>
  );
}

export default function AdminUsersPage() {
  return (
    <RequireAuth>
      <AdminUsersContent />
    </RequireAuth>
  );
}