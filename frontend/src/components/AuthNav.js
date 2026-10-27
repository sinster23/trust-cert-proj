"use client";

import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";

export default function AuthNav() {
  const { status, user, logout } = useAuth();

  if (status === "loading") return <div className="h-9 w-24" aria-hidden="true" />;

  if (status === "anonymous") {
    return (
      <Link
        href="/login"
        className="rounded-md bg-brand px-4 py-2 font-medium text-white hover:bg-brand-dark"
      >
        Sign in
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-5">
      <Link href="/dashboard" className="text-muted hover:text-brand-dark">
        Dashboard
      </Link>
      <span className="hidden max-w-[14rem] truncate text-muted sm:inline" title={user?.email}>
        {user?.email}
      </span>
      <button
        type="button"
        onClick={logout}
        className="rounded-md border border-line px-4 py-2 font-medium text-brand-dark hover:bg-brand-soft"
      >
        Sign out
      </button>
    </div>
  );
}