import Link from "next/link";
import AuthNav from "@/components/AuthNav";

export default function SiteHeader() {
  return (
    <header className="border-b border-line bg-white">
      <div className="h-1.5 bg-brand-dark" />
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex flex-col leading-tight">
          <span className="font-serif text-2xl font-semibold tracking-tight text-brand-dark">
            Credence
          </span>
          <span className="text-xs uppercase tracking-widest text-muted">
            Academic Certificate Registry
          </span>
        </Link>
        <nav className="flex items-center gap-6 text-sm">
          <Link href="/" className="text-muted hover:text-brand-dark">
            Home
          </Link>
          <AuthNav />
        </nav>
      </div>
    </header>
  );
}