"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { normalizeCertificateId } from "@/lib/verify";

const INVALID_ID_MESSAGE =
  "Enter a valid Certificate ID (CERT- followed by 32 hexadecimal characters).";

export default function CertificateVerifier({ initialId = "", initialError = "" }) {
  const router = useRouter();
  const [value, setValue] = useState(initialId);
  const [inputError, setInputError] = useState(initialError);
  const [going, setGoing] = useState(false);
  const submitted = useRef(false);

  function onSubmit(e) {
    e.preventDefault();
    if (submitted.current) return;
    const id = normalizeCertificateId(value);
    if (!id) {
      setInputError(INVALID_ID_MESSAGE);
      return;
    }
    submitted.current = true;
    setGoing(true);
    router.push(`/verify/${id}`);
  }

  return (
    <form onSubmit={onSubmit} noValidate className="mt-10 max-w-2xl space-y-3">
      <label htmlFor="verify-id" className="block text-sm font-medium text-ink">
        Certificate ID
      </label>
      <input
        id="verify-id"
        type="text"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setInputError("");
        }}
        disabled={going}
        maxLength={100}
        placeholder="Enter Certificate ID (e.g. CERT-xxxxxxxx...)"
        autoComplete="off"
        autoCapitalize="off"
        spellCheck={false}
        aria-invalid={inputError ? "true" : undefined}
        aria-describedby={inputError ? "verify-id-error" : undefined}
        className={`w-full rounded-md border bg-white px-3 py-3 font-mono text-sm text-ink placeholder:text-muted/60 focus:border-brand disabled:bg-brand-soft ${
          inputError ? "border-red-400" : "border-line"
        }`}
      />
      {inputError && (
        <p id="verify-id-error" role="alert" className="text-sm text-red-700">
          {inputError}
        </p>
      )}
      <button
        type="submit"
        disabled={value.trim() === "" || going}
        className="rounded-md bg-brand px-6 py-3 font-medium text-white hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-50"
      >
        {going ? "Opening result..." : "Verify Certificate"}
      </button>
    </form>
  );
}