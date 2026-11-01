// "2025-06-15" -> "15 June 2025" (calendar date, no timezone shifting).
export function formatIsoDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso ?? "");
  if (!m) return String(iso ?? "");
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  return new Date(Date.UTC(y, mo - 1, d)).toLocaleDateString("en-GB", {
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  });
}