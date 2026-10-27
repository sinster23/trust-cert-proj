"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

// Wrap any page that needs a signed-in user. Redirects to /login otherwise.
export default function RequireAuth({ children }) {
  const router = useRouter();
  const { status } = useAuth();

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  if (status !== "authenticated") {
    return (
      <p className="mx-auto max-w-6xl px-6 py-16 text-muted">Loading&hellip;</p>
    );
  }
  return children;
}