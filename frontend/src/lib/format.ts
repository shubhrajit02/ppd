export function duration(value: number | undefined) {
  if (value === undefined) return "—";
  return value < 60 ? `${value.toFixed(1)}s` : `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
}
export function date(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
export function label(value: string) { return value.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase()); }
