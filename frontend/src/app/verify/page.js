import { redirect } from "next/navigation";
import CertificateVerifier from "@/components/CertificateVerifier";
import { normalizeCertificateId } from "@/lib/verify";

export const metadata = {
  title: "Verify Certificate | Credence",
  description: "Verify an academic certificate using its Certificate ID.",
};

// /verify is only the form. Old /verify?id=CERT-... links redirect to /verify/<id>;
// an invalid id stays here, prefilled, with an error.
export default async function VerifyPage({ searchParams }) {
  const { id } = await searchParams;
  const raw = typeof id === "string" ? id.trim().slice(0, 100) : "";

  const normalized = raw ? normalizeCertificateId(raw) : null;
  if (normalized) redirect(`/verify/${normalized}`);

  return (
    <section className="bg-brand-soft">
      <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
        <p className="mb-4 text-xs font-medium uppercase tracking-widest text-brand">
          Public verification
        </p>
        <h1 className="max-w-2xl font-serif text-4xl font-semibold leading-tight text-brand-dark">
          Verify Academic Certificate
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-muted">
          Enter the unique Certificate ID printed on the certificate to check its
          authenticity against Credence&apos;s official records.
        </p>

        <CertificateVerifier
          initialId={raw}
          initialError={
            raw
              ? "Enter a valid Certificate ID (CERT- followed by 32 hexadecimal characters)."
              : ""
          }
        />

        <p className="mt-10 max-w-2xl text-sm leading-relaxed text-muted">
          This page verifies the certificate record held by Credence. It does not
          verify a PDF, scan or printed copy. Knowing a Certificate ID is not proof
          of ownership: it does not show that the person holding a certificate is
          the named graduate.
        </p>
      </div>
    </section>
  );
}