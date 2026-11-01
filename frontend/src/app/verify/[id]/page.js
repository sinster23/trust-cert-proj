import Link from "next/link";
import { redirect } from "next/navigation";
import VerificationPanel from "@/components/VerificationPanel";
import VerificationResult from "@/components/VerificationResult";
import { normalizeCertificateId } from "@/lib/verify";

// Result pages can show a graduate's details: keep them out of search engines.
export const metadata = {
  title: "Certificate Verification | Credence",
  description: "Result of a Credence certificate verification.",
  robots: { index: false, follow: false },
};

function safeDecode(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export default async function VerifyResultPage({ params }) {
  const { id: rawParam } = await params;
  const raw = safeDecode(rawParam);
  const id = normalizeCertificateId(raw);

  if (id && id !== raw) redirect(`/verify/${id}`); // one canonical URL per certificate

  return (
    <section className="bg-brand-soft">
      <div className="mx-auto max-w-4xl px-6 py-12 sm:py-16">
        <p className="mb-3 text-xs font-medium uppercase tracking-widest text-brand">
          Public verification
        </p>
        <h1 className="font-serif text-3xl font-semibold leading-tight text-brand-dark sm:text-4xl">
          Certificate Verification
        </h1>

        <div className="mt-8">
          {id ? (
            <VerificationResult id={id} />
          ) : (
            <VerificationPanel outcome={{ type: "invalid-id" }} />
          )}
        </div>

        <p className="no-print mt-10 text-sm">
          <Link href="/verify" className="font-medium text-brand underline">
            Verify another certificate
          </Link>
        </p>
      </div>
    </section>
  );
}