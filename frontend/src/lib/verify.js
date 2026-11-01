// Public certificate verification: no login, no token.
// Talks to GET /certificates/verify/{certificate_id}.
//
// Backend contract:
//   body:  { certificate_id, status, signature_valid, certificate_status,
//            message, details_available, certificate_details }
//   HTTP:  200 VALID | INVALID | REVOKED, 404 NOT_FOUND, 503 UNVERIFIABLE
//          422 malformed id, 429 rate limited (Retry-After), 500 inconsistent record
//   certificate_details: exactly seven strings for VALID/REVOKED when the backend
//   switch VERIFICATION_SHOW_DETAILS is on, otherwise null. student_id is masked.
//
// Fails closed: a response that is malformed, self-contradictory or carries
// details it should not have is an error, never a result. The returned result is
// rebuilt from known fields only.

export const REQUEST_TIMEOUT_MS = 15000;

const STATUSES = ["VALID", "INVALID", "REVOKED", "NOT_FOUND", "UNVERIFIABLE"];
const EXPECTED_HTTP = { VALID: 200, INVALID: 200, REVOKED: 200, NOT_FOUND: 404, UNVERIFIABLE: 503 };
const ID_FORMAT = /^cert-([0-9a-f]{32})$/i;

export function normalizeCertificateId(raw) {
  if (typeof raw !== "string") return null;
  const match = ID_FORMAT.exec(raw.trim());
  return match ? `CERT-${match[1].toLowerCase()}` : null;
}

const RESPONSE_KEYS = [
  "certificate_id", "status", "signature_valid", "certificate_status",
  "message", "details_available", "certificate_details",
];
export const DETAIL_KEYS = [
  "student_id", "student_name", "institution", "degree",
  "field_of_study", "graduation_date", "issue_date",
];
const DETAIL_STATUSES = ["VALID", "REVOKED"];
const MAX_TEXT = 400;
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;
// Backend always sends six asterisks and at most four visible characters.
const MASKED_STUDENT_ID = /^\*{6}[A-Za-z0-9._/-]{0,4}$/;

const hasExactKeys = (obj, keys) => {
  const actual = Object.keys(obj);
  return actual.length === keys.length && keys.every((k) => Object.hasOwn(obj, k));
};

const isText = (v) => typeof v === "string" && v.trim() !== "" && v.length <= MAX_TEXT;

function isCalendarDate(v) {
  const m = typeof v === "string" ? ISO_DATE.exec(v) : null;
  if (!m) return false;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const date = new Date(Date.UTC(y, mo - 1, d));
  return date.getUTCFullYear() === y && date.getUTCMonth() === mo - 1 && date.getUTCDate() === d;
}

// Clean copy of the details, or null if not exactly the seven public fields.
function readDetails(d) {
  if (d === null || typeof d !== "object" || Array.isArray(d)) return null;
  if (!hasExactKeys(d, DETAIL_KEYS)) return null;
  const textOk = ["student_name", "institution", "degree", "field_of_study"].every((k) =>
    isText(d[k]),
  );
  if (!textOk) return null;
  if (typeof d.student_id !== "string" || !MASKED_STUDENT_ID.test(d.student_id)) return null;
  if (!isCalendarDate(d.graduation_date) || !isCalendarDate(d.issue_date)) return null;
  return Object.fromEntries(DETAIL_KEYS.map((k) => [k, d[k]]));
}

function isStandardResponse(d) {
  return (
    d !== null &&
    typeof d === "object" &&
    !Array.isArray(d) &&
    hasExactKeys(d, RESPONSE_KEYS) &&
    typeof d.certificate_id === "string" &&
    STATUSES.includes(d.status) &&
    (d.signature_valid === null || typeof d.signature_valid === "boolean") &&
    (d.certificate_status === null ||
      d.certificate_status === "ACTIVE" ||
      d.certificate_status === "REVOKED") &&
    typeof d.message === "string" &&
    typeof d.details_available === "boolean"
  );
}

function isConsistent(d) {
  switch (d.status) {
    case "VALID":
      return d.signature_valid === true && d.certificate_status === "ACTIVE";
    case "REVOKED":
      return d.signature_valid === true && d.certificate_status === "REVOKED";
    case "INVALID":
      return d.signature_valid === false;
    default: // NOT_FOUND, UNVERIFIABLE
      return d.signature_valid !== true && d.certificate_status === null;
  }
}

// Details only for VALID/REVOKED, and details_available must tell the truth.
function readDetailsContract(d) {
  if (!d.details_available) {
    return d.certificate_details === null ? { details: null } : null;
  }
  if (!DETAIL_STATUSES.includes(d.status)) return null;
  const details = readDetails(d.certificate_details);
  return details ? { details } : null;
}

const error = (reason) => ({ type: "error", reason });

function interpret(httpStatus, data, id, retryAfter) {
  if (httpStatus === 422) return { type: "invalid-id" };

  if ([200, 404, 503].includes(httpStatus) && isStandardResponse(data)) {
    if (EXPECTED_HTTP[data.status] !== httpStatus) return error("unexpected");
    if (data.certificate_id !== id) return error("unexpected");
    if (!isConsistent(data)) return error("unexpected");
    const contract = readDetailsContract(data);
    if (!contract) return error("unexpected");
    return {
      type: "result",
      result: {
        certificate_id: data.certificate_id,
        status: data.status,
        signature_valid: data.signature_valid,
        certificate_status: data.certificate_status,
        message: data.message,
        details_available: data.details_available,
        details: contract.details,
      },
    };
  }

  if (httpStatus === 429) return { ...error("rate-limit"), retryAfter };
  if (httpStatus === 401 || httpStatus === 403) return error("access");
  if (httpStatus === 502) return error("gateway");
  if (httpStatus === 504) return error("timeout");
  if (httpStatus === 503) return error("unavailable");
  if (httpStatus >= 500) return error("server");
  if (httpStatus >= 400) return error("request");
  return error("unexpected");
}

function readRetryAfter(res) {
  const raw = res.headers.get("retry-after");
  if (!raw || !/^\d{1,4}$/.test(raw.trim())) return null;
  const seconds = Number(raw);
  return seconds > 0 ? seconds : null;
}

// Returns { type: "result", result } | { type: "invalid-id" } |
//   { type: "error", reason, retryAfter? } | { type: "aborted" }
export async function verifyCertificate(certificateId, { signal } = {}) {
  const id = normalizeCertificateId(certificateId);
  if (!id) return { type: "invalid-id" };

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);
  const forwardAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", forwardAbort, { once: true });
  }

  const failure = () =>
    timedOut ? error("timeout") : signal?.aborted ? { type: "aborted" } : error("network");

  try {
    let res;
    try {
      res = await fetch(`/api/certificates/verify/${encodeURIComponent(id)}`, {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
        signal: controller.signal,
      });
    } catch {
      return failure();
    }

    let data = null;
    try {
      data = await res.json();
    } catch {
      if (controller.signal.aborted) return failure();
    }
    return interpret(res.status, data, id, readRetryAfter(res));
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", forwardAbort);
  }
}