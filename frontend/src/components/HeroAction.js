"use client";

import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";

export default function HeroAction() {
  const { status } = useAuth();
  const signedIn = status === "authenticated";
  return (
    <Link
      href={signedIn ? "/dashboard" : "/login"}
      className="rounded-md bg-brand px-6 py-3 font-medium text-white hover:bg-brand-dark"
    >
      {signedIn ? "Go to dashboard" : "Sign in"}
    </Link>
  );
}