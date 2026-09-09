const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });
const shortFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });
const monthFmt = new Intl.DateTimeFormat("en-GB", { month: "short", year: "2-digit" });

const safe = (fmt: Intl.DateTimeFormat) => (iso: string) => {
  const date = new Date(`${iso}T00:00:00`);
  return Number.isNaN(date.getTime()) ? "" : fmt.format(date);
};

export const fmtDate = safe(dateFmt);
export const fmtShort = safe(shortFmt);
export const fmtMonth = safe(monthFmt);
export const fmtNum = (n: number | null | undefined, digits = 1) =>
  n === null || n === undefined ? "–" : n.toLocaleString("en-GB", { maximumFractionDigits: digits });
export const fmtSigned = (n: number | null | undefined, digits = 1) =>
  n === null || n === undefined ? "–" : `${n > 0 ? "+" : n < 0 ? "−" : "±"}${fmtNum(Math.abs(n), digits)}`;

export const titleCase = (s: string) => s.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase());
