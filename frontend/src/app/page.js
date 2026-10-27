import Link from "next/link";
import HeroAction from "@/components/HeroAction";

const steps = [
  {
    n: "01",
    title: "Sign in",
    text: "Use your institutional Google account. Access is limited to the institute's domain.",
  },
  {
    n: "02",
    title: "Issue",
    text: "Authorised issuers enter the graduate's details. The system generates the certificate ID.",
  },
  {
    n: "03",
    title: "Sign and store",
    text: "Each certificate is digitally signed and recorded, so any change can be detected.",
  },
];

export default function Home() {
  return (
    <>
      <section className="border-b border-line bg-brand-soft">
        <div className="mx-auto max-w-6xl px-6 py-20 sm:py-28">
          <p className="mb-4 text-xs font-medium uppercase tracking-widest text-brand">
            Office of the Registrar
          </p>
          <h1 className="max-w-2xl font-serif text-4xl font-semibold leading-tight text-brand-dark sm:text-5xl">
            Academic certificates that can be trusted.
          </h1>
          <p className="mt-6 max-w-xl text-lg text-muted">
            Credence issues digitally signed degree certificates for the
            institute, so every record can be checked and none can be quietly
            altered.
          </p>
          <div className="mt-10 flex flex-wrap gap-4">
            <HeroAction />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-16">
        <h2 className="font-serif text-2xl font-semibold text-brand-dark">
          How it works
        </h2>
        <ol className="mt-8 grid gap-6 sm:grid-cols-3">
          {steps.map((s) => (
            <li key={s.n} className="rounded-lg border border-line bg-white p-6">
              <span className="font-serif text-3xl text-brand">{s.n}</span>
              <h3 className="mt-3 text-lg font-semibold text-ink">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{s.text}</p>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}