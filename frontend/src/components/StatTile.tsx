export function StatTile({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: number | string;
  tone?: "default" | "warning" | "critical";
}) {
  const valueColor =
    tone === "critical" ? "text-red-600" : tone === "warning" ? "text-amber-600" : "text-gray-900";
  return (
    <div className="rounded-md border border-gray-200 bg-white p-4">
      <div className={`text-2xl font-semibold ${valueColor}`}>{value}</div>
      <div className="mt-1 text-xs text-gray-500">{label}</div>
    </div>
  );
}

/** Categorical breakdown bars -- color follows the entity (opportunity type,
 * website status, etc.), reusing the same fixed hue assignment as the
 * badges elsewhere in the app, never a generated/cycled color. */
export function BreakdownBars({
  data,
  colorClass,
}: {
  data: { label: string; count: number }[];
  colorClass: (label: string) => string;
}) {
  const total = data.reduce((sum, d) => sum + d.count, 0) || 1;
  if (data.length === 0) {
    return <p className="text-sm text-gray-400">No data yet.</p>;
  }
  return (
    <div className="space-y-2">
      {data.map((d) => (
        <div key={d.label} className="flex items-center gap-3 text-sm">
          <span className="w-44 shrink-0 truncate text-gray-600" title={d.label.replaceAll("_", " ")}>
            {d.label.replaceAll("_", " ")}
          </span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
            <div
              className={`h-full rounded-full ${colorClass(d.label)}`}
              style={{ width: `${(d.count / total) * 100}%` }}
            />
          </div>
          <span className="w-8 shrink-0 text-right text-gray-500">{d.count}</span>
        </div>
      ))}
    </div>
  );
}
