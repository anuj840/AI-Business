"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type PaginatedBusinesses, ApiError } from "@/lib/api";
import { DealStatusBadge } from "@/components/Badge";

const PAGE_SIZE = 25;

export default function DashboardPage() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedBusinesses | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Derived rather than a separate setState call in the effect below: the
  // page we're showing data for hasn't caught up to the requested page
  // while a fetch for the new page is in flight.
  const loading = data === null || data.page !== page;

  useEffect(() => {
    let cancelled = false;
    api
      .listBusinesses(page, PAGE_SIZE)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load businesses.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [page]);

  // Deliberately shows the previous page's items (dimmed via the `loading`
  // flag below) while a new page loads, rather than flashing empty.
  const businesses = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">
          Prospect Dashboard
          {data && data.total > 0 && (
            <span className="ml-2 text-base font-normal text-gray-400">
              ({data.total} total)
            </span>
          )}
        </h1>
        <Link
          href="/businesses/new"
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
        >
          + New Business
        </Link>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}. Is the backend running at{" "}
          <code className="font-mono">{process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}</code>?
        </div>
      )}

      {loading && !data && (
        <div className="rounded-md border border-gray-200 bg-white p-6 text-sm text-gray-500">
          Loading businesses…
        </div>
      )}

      {data && data.total === 0 && (
        <div className="rounded-md border border-dashed border-gray-300 bg-white p-10 text-center">
          <p className="text-gray-600">No businesses yet.</p>
          <p className="mt-1 text-sm text-gray-400">
            Add a business by name and (optionally) website URL to run the analysis
            pipeline against it.
          </p>
          <Link
            href="/businesses/new"
            className="mt-4 inline-block rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
          >
            Add your first business
          </Link>
        </div>
      )}

      {data && data.total > 0 && (
        <div className={`overflow-hidden rounded-md border border-gray-200 bg-white ${loading ? "opacity-50" : ""}`}>
          <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">Industry</th>
                <th className="px-4 py-3">Website</th>
                <th className="px-4 py-3">Domain Age</th>
                <th className="px-4 py-3">Contact</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Added</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {businesses.map((b) => (
                <tr key={b.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link
                      href={`/businesses/${b.id}`}
                      className="font-medium text-gray-900 hover:underline"
                    >
                      {b.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {[b.city, b.region, b.country].filter(Boolean).join(", ") || "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{b.industry ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {b.submitted_website_url ? "Provided" : "None"}
                  </td>
                  <td className="px-4 py-3">
                    {b.domain_age_years != null ? (
                      <span
                        className={
                          b.domain_age_years >= 10
                            ? "inline-flex items-center rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-600/20"
                            : "text-gray-500"
                        }
                        title={
                          b.domain_age_years >= 10
                            ? "Old domain — likely due a design refresh"
                            : undefined
                        }
                      >
                        {b.domain_age_years.toFixed(0)}y
                      </span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {b.phone || b.email ? (
                      <span className="inline-flex items-center rounded-md bg-green-50 px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">
                        Reachable
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-md bg-gray-100 px-2 py-1 text-xs font-medium text-gray-500 ring-1 ring-inset ring-gray-400/20">
                        No contact
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <DealStatusBadge status={b.deal_status} />
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {new Date(b.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>

          {data.total_pages > 1 && (
            <div className="flex items-center justify-between border-t border-gray-200 px-4 py-3 text-sm text-gray-500">
              <span>
                Page {data.page} of {data.total_pages}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1 || loading}
                  className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                  disabled={page >= data.total_pages || loading}
                  className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
