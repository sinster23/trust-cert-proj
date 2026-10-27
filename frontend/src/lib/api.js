// Thin wrapper around fetch for the Credence API.
// All calls go to /api/*, which Next.js forwards to FastAPI (see next.config.mjs).

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiFetch(path, { token, method = "GET", body } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Could not reach the server.");
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    // empty or non-JSON body
  }

  if (!res.ok) {
    let detail = "Request failed.";
    if (data && typeof data.detail === "string") {
      detail = data.detail;
    } else if (data && Array.isArray(data.detail) && data.detail[0]?.msg) {
      // FastAPI schema errors: [{ loc: [...], msg: "..." }]
      const field = data.detail[0].loc?.slice(-1)[0];
      detail = field ? `${field}: ${data.detail[0].msg}` : data.detail[0].msg;
    }
    throw new ApiError(res.status, detail);
  }
  return data;
}