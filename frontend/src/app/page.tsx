"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Business, ApiError } from "@/lib/api";

export default function DashboardPage() {
  const [businesses, setBusinesses] = useState<Business[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listBusinesses()
      .then((data) => {
        if (!cancelled) setBusinesses(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load businesses.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Prospect Dashboard</h1>
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

      {!businesses && !error && (
        <div className="rounded-md border border-gray-200 bg-white p-6 text-sm text-gray-500">
          Loading businesses…
        </div>
      )}

      {businesses && businesses.length === 0 && (
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

      {businesses && businesses.length > 0 && (
        <div className="overflow-hidden rounded-md border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">Industry</th>
                <th className="px-4 py-3">Website</th>
                <th className="px-4 py-3">Contact</th>
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
                  <td className="px-4 py-3 text-gray-400">
                    {new Date(b.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
