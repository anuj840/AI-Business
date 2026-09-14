const OPPORTUNITY_STYLES: Record<string, string> = {
  NEW_WEBSITE: "bg-blue-50 text-blue-700 ring-blue-600/20",
  WEBSITE_REDESIGN: "bg-amber-50 text-amber-700 ring-amber-600/20",
  WEBSITE_OPTIMIZATION: "bg-amber-50 text-amber-700 ring-amber-600/20",
  LEAD_CONVERSION: "bg-purple-50 text-purple-700 ring-purple-600/20",
  AI_AUTOMATION: "bg-teal-50 text-teal-700 ring-teal-600/20",
  SEO_GROWTH: "bg-indigo-50 text-indigo-700 ring-indigo-600/20",
  OTHER_SERVICE: "bg-gray-50 text-gray-700 ring-gray-600/20",
  IGNORE: "bg-gray-100 text-gray-500 ring-gray-400/20",
};

const WEBSITE_STATUS_STYLES: Record<string, string> = {
  WEBSITE_FOUND: "bg-green-50 text-green-700 ring-green-600/20",
  NO_WEBSITE_FOUND: "bg-red-50 text-red-700 ring-red-600/20",
  WEBSITE_UNCERTAIN: "bg-yellow-50 text-yellow-700 ring-yellow-600/20",
  WEBSITE_UNAVAILABLE: "bg-red-50 text-red-700 ring-red-600/20",
};

const KIND_STYLES: Record<string, string> = {
  FACT: "bg-slate-100 text-slate-700 ring-slate-500/20",
  AI_INFERENCE: "bg-sky-50 text-sky-700 ring-sky-600/20",
  RECOMMENDATION: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
};

const PRIORITY_STYLES: Record<string, string> = {
  HIGH_PRIORITY: "bg-red-50 text-red-700 ring-red-600/20",
  GOOD: "bg-amber-50 text-amber-700 ring-amber-600/20",
  MEDIUM: "bg-blue-50 text-blue-700 ring-blue-600/20",
  LOW: "bg-gray-50 text-gray-500 ring-gray-400/20",
};

function Badge({
  label,
  className,
}: {
  label: string;
  className: string;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${className}`}
    >
      {label.replaceAll("_", " ")}
    </span>
  );
}

export function OpportunityBadge({ type }: { type: string }) {
  return (
    <Badge
      label={type}
      className={OPPORTUNITY_STYLES[type] ?? "bg-gray-50 text-gray-700 ring-gray-600/20"}
    />
  );
}

export function WebsiteStatusBadge({ status }: { status: string }) {
  return (
    <Badge
      label={status}
      className={WEBSITE_STATUS_STYLES[status] ?? "bg-gray-50 text-gray-700 ring-gray-600/20"}
    />
  );
}

export function AuditItemKindBadge({ kind }: { kind: string }) {
  return (
    <Badge label={kind} className={KIND_STYLES[kind] ?? "bg-gray-50 text-gray-700 ring-gray-600/20"} />
  );
}

export function PriorityBadge({ priority }: { priority: string }) {
  return (
    <Badge
      label={priority}
      className={PRIORITY_STYLES[priority] ?? "bg-gray-50 text-gray-700 ring-gray-600/20"}
    />
  );
}
