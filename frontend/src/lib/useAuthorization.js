"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";

// Loads the signed-in user's role and permissions from the backend (M2).
// `can(permission)` is for showing or hiding UI only; the API enforces access.
export function useAuthorization() {
  const { status, authFetch } = useAuth();
  const [state, setState] = useState({ loading: true, error: "", role: null, permissions: [] });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (status !== "authenticated") return;
    let cancelled = false;
    async function load() {
      try {
        const data = await authFetch("/authorization/me");
        if (!cancelled)
          setState({ loading: false, error: "", role: data.role, permissions: data.permissions });
      } catch (err) {
        if (!cancelled)
          setState({
            loading: false,
            error:
              err?.status === 401
                ? ""
                : "Could not load your access details. Please try again.",
            role: null,
            permissions: [],
          });
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [status, authFetch, attempt]);

  const retry = useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: "" }));
    setAttempt((n) => n + 1);
  }, []);

  const can = useCallback((permission) => state.permissions.includes(permission), [state.permissions]);

  return { ...state, can, retry };
}