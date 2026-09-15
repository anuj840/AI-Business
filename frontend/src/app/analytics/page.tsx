"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError, type AnalyticsSummary, type HotDeal } from "@/lib/api";
import { OpportunityBadge, PriorityBadge, DealStatusBadge } from "@/components/Badge";
import { BreakdownBars, StatTile } from "@/components/StatTile";

const OPPORTUNITY_FILL: Record<string, string> = {
  NEW_WEBSITE: "bg-blue-500",
  WEBSITE_REDESIGN: "bg-amber-500",
  WEBSITE_OPTIMIZATION: "bg-amber-500",
  LEAD_CONVERSION: "bg-purple-500",
  AI_AUTOMATION: "bg-teal-500",
  SEO_GROWTH: "bg-indigo-500",
  OTHER_SERVICE: "bg-gray-400",
  IGNORE: "bg-gray-300",
};

const WEBSITE_STATUS_FILL: Record<string, string> = {
  WEBSITE_FOUND: "bg-green-500",
  NO_WEBSITE_FOUND: "bg-red-500",
  WEBSITE_UNCERTAIN: "bg-yellow-500",
  WEBSITE_UNAVAILABLE: "bg-red-400",
};

const PRIORITY_FILL: Record<string, string> = {
  HIGH_PRIORITY: "bg-red-500",
  GOOD: "bg-amber-500",
  MEDIUM: "bg-blue-500",
  LOW: "bg-gray-400",
};

const PRIORITY_ORDER = ["HIGH_PRIORITY", "GOOD", "MEDIUM", "LOW"];

const DEAL_STATUS_FILL: Record<string, string> = {
  NEW: "bg-gray-400",
  CONTACTED: "bg-blue-500",
  REPLIED: "bg-indigo-500",
  INTERESTED: "bg-purple-500",
  NOT_INTERESTED: "bg-gray-300",
  DO_NOT_CONTACT: "bg-red-500",
  CONVERTED: "bg-green-500",
};
const DEAL_STATUS_ORDER = [
  "NEW",
  "CONTACTED",
  "REPLIED",
  "INTERESTED",
  "CONVERTED",
  "NOT_INTERESTED",
  "DO_NOT_CONTACT",
];

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [hotDeals, setHotDeals] = useState<HotDeal[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getAnalyticsSummary(), api.getHotDeals(20)])
      .then(([s, deals]) => {
        if (cancelled) return;
        setSummary(s);
        setHotDeals(deals);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load analytics.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!summary || !hotDeals) {
    return <div className="text-sm text-gray-500">Loading analytics…</div>;
  }

  const opportunityData = Object.entries(summary.opportunity_breakdown).map(([label, count]) => ({
    label,
    count,
  }));
  const websiteStatusData = Object.entries(summary.website_status_breakdown).map(
    ([label, count]) => ({ label, count })
  );
  const priorityData = PRIORITY_ORDER.filter(
    (label) => summary.priority_tier_breakdown[label] > 0
  ).map((label) => ({ label, count: summary.priority_tier_breakdown[label] }));
  const dealStatusData = DEAL_STATUS_ORDER.filter(
    (label) => summary.deal_status_breakdown[label] > 0
  ).map((label) => ({ label, count: summary.deal_status_breakdown[label] }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Analytics</h1>
        <p className="mt-1 text-sm text-gray-500">
          Where your pipeline stands today, and which leads are most worth working
          right now.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile label="Total businesses" value={summary.total_businesses} />
        <StatTile label="Analyzed" value={summary.analyzed} />
        <StatTile label="Not yet analyzed" value={summary.not_analyzed} tone="warning" />
        <StatTile label="Reachable" value={summary.reachable} />
        <StatTile
          label="Drafts approved"
          value={`${summary.outreach_drafts_approved} / ${summary.outreach_drafts_total}`}
        />
        <StatTile
          label="Failed jobs"
          value={summary.jobs_failed}
          tone={summary.jobs_failed > 0 ? "critical" : "default"}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <section className="rounded-md border border-gray-200 bg-white p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Opportunity type
          </h2>
          <div className="mt-4">
            <BreakdownBars data={opportunityData} colorClass={(l) => OPPORTUNITY_FILL[l] ?? "bg-gray-400"} />
          </div>
        </section>

        <section className="rounded-md border border-gray-200 bg-white p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Website status
          </h2>
          <div className="mt-4">
            <BreakdownBars
              data={websiteStatusData}
              colorClass={(l) => WEBSITE_STATUS_FILL[l] ?? "bg-gray-400"}
            />
          </div>
        </section>

        <section className="rounded-md border border-gray-200 bg-white p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Priority tier (analyzed only)
          </h2>
          <div className="mt-4">
            <BreakdownBars data={priorityData} colorClass={(l) => PRIORITY_FILL[l] ?? "bg-gray-400"} />
          </div>
        </section>

        <section className="rounded-md border border-gray-200 bg-white p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Deal status
          </h2>
          <div className="mt-4">
            <BreakdownBars
              data={dealStatusData}
              colorClass={(l) => DEAL_STATUS_FILL[l] ?? "bg-gray-400"}
            />
          </div>
        </section>
      </div>

      <section>
        <h2 className="text-lg font-semibold">Hot Deals</h2>
        <p className="mt-1 text-sm text-gray-500">
          Highest lead score, reachable by phone or email, a real opportunity, not yet
          approved for outreach — sorted best first.
        </p>

        {hotDeals.length === 0 ? (
          <div className="mt-4 rounded-md border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-500">
            No hot deals yet. Run analysis on more businesses, or check contact info on
            businesses that don&apos;t have it yet.
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto rounded-md border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Score</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Opportunity</th>
                  <th className="px-4 py-3">Domain Age</th>
                  <th className="px-4 py-3">Service</th>
                  <th className="px-4 py-3">Contact</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {hotDeals.map((deal) => (
                  <tr key={deal.business_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <Link
                        href={`/businesses/${deal.business_id}`}
                        className="font-medium text-gray-900 hover:underline"
                      >
                        {deal.name}
                      </Link>
                      <div className="text-xs text-gray-400">
                        {[deal.city, deal.region].filter(Boolean).join(", ")}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-medium text-gray-700">{deal.lead_score}</td>
                    <td className="px-4 py-3">
                      <PriorityBadge priority={deal.priority} />
                    </td>
                    <td className="px-4 py-3">
                      <DealStatusBadge status={deal.deal_status} />
                    </td>
                    <td className="px-4 py-3">
                      <OpportunityBadge type={deal.opportunity_type} />
                    </td>
                    <td className="px-4 py-3">
                      {deal.domain_age_years != null ? (
                        <span
                          className={
                            deal.domain_age_years >= 10
                              ? "inline-flex items-center rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-600/20"
                              : "text-gray-500"
                          }
                        >
                          {deal.domain_age_years.toFixed(0)}y
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500">{deal.recommended_service ?? "—"}</td>
                    <td className="px-4 py-3 text-gray-500">
                      {[deal.phone, deal.email].filter(Boolean).join(" · ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
