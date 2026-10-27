"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, apiFetch } from "@/lib/api";

const TOKEN_KEY = "credence.token";
const AuthContext = createContext(null);

function readToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeToken(token) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage unavailable: the session simply won't survive a reload
  }
}

export function AuthProvider({ children }) {
  const router = useRouter();
  const [state, setState] = useState({ status: "loading", token: null, user: null });

  // Restore a session on first load by asking the backend who the token belongs to.
  useEffect(() => {
    let cancelled = false;
    async function restore() {
      const token = readToken();
      if (!token) {
        setState({ status: "anonymous", token: null, user: null });
        return;
      }
      try {
        const user = await apiFetch("/auth/me", { token });
        if (!cancelled) setState({ status: "authenticated", token, user });
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) writeToken(null);
        if (!cancelled) setState({ status: "anonymous", token: null, user: null });
      }
    }
    restore();
    return () => {
      cancelled = true;
    };
  }, []);

  // Exchange a Google ID token for a Credence token. Throws ApiError on failure.
  const login = useCallback(async (idToken) => {
    const data = await apiFetch("/auth/google", {
      method: "POST",
      body: { id_token: idToken },
    });
    writeToken(data.access_token);
    setState({ status: "authenticated", token: data.access_token, user: data.user });
    return data.user;
  }, []);

  const logout = useCallback(() => {
    writeToken(null);
    setState({ status: "anonymous", token: null, user: null });
    router.push("/");
  }, [router]);

  // Authenticated request helper: adds the token and signs out on 401 (expired/invalid).
  const authFetch = useCallback(
    async (path, options = {}) => {
      try {
        return await apiFetch(path, { ...options, token: state.token });
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          writeToken(null);
          setState({ status: "anonymous", token: null, user: null });
          router.push("/login");
        }
        throw err;
      }
    },
    [state.token, router],
  );

  const value = useMemo(
    () => ({ ...state, login, logout, authFetch }),
    [state, login, logout, authFetch],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}