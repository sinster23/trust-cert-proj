import { isIP } from "node:net";

export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const UPSTREAM_TIMEOUT_MS = 10000;
const ID_FORMAT = /^CERT-[0-9a-f]{32}$/;

// Number of proxies YOU operate in front of Next.js. Default 0 is safe: Next only
// adds X-Forwarded-For when absent, so a directly exposed Next.js is spoofable.
function trustedHops() {
  const n = Number.parseInt(process.env.TRUSTED_PROXY_HOPS ?? "0", 10);
  return Number.isInteger(n) && n >= 0 && n <= 10 ? n : 0;
}

// Read from the RIGHT, never the left (the left is forgeable).
function clientIpFrom(forwardedFor, hops) {
  if (hops < 1 || !forwardedFor) return null;
  const parts = forwardedFor.split(",").map((p) => p.trim());
  if (parts.length < hops) return null;
  const candidate = parts[parts.length - hops];
  return isIP(candidate) ? candidate : null;
}

function json(status, body, extra = {}) {
  return Response.json(body, { status, headers: { "Cache-Control": "no-store", ...extra } });
}

export async function GET(request, { params }) {
  const { id } = await params;
  if (!ID_FORMAT.test(id)) return json(422, { detail: "Invalid certificate ID" });

  // Built from scratch: nothing the browser sent is forwarded.
  const headers = { Accept: "application/json" };
  const secret = process.env.VERIFICATION_PROXY_SECRET;
  const ip = clientIpFrom(request.headers.get("x-forwarded-for"), trustedHops());
  if (secret && ip) {
    headers["X-Credence-Client-IP"] = ip;
    headers["X-Credence-Proxy-Secret"] = secret;
  }

  let upstream;
  try {
    upstream = await fetch(`${BACKEND_URL}/certificates/verify/${encodeURIComponent(id)}`, {
      method: "GET", headers, cache: "no-store",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
  } catch (err) {
    const timedOut = err?.name === "TimeoutError" || err?.name === "AbortError";
    return json(timedOut ? 504 : 502, { detail: "Verification service did not respond" });
  }

  const extra = { "Content-Type": upstream.headers.get("content-type") || "application/json" };
  const retryAfter = upstream.headers.get("retry-after");
  if (retryAfter) extra["Retry-After"] = retryAfter;
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "Cache-Control": "no-store", ...extra },
  });
}