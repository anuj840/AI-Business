"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { api, ApiError, type DiscoveryResult } from "@/lib/api";

const inputClass =
  "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500";
const labelClass = "block text-sm font-medium text-gray-700 mb-1";

export default function DiscoverPage() {
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DiscoveryResult | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);
    setSearching(true);

    const form = new FormData(event.currentTarget);
    const country = String(form.get("country") ?? "").trim();
    const industry = String(form.get("industry") ?? "").trim();
    if (!country || !industry) {
      setError("Country and industry are required.");
      setSearching(false);
      return;
    }

    try {
      const data = await api.runDiscovery({
        country,
        region: emptyToUndefined(form.get("region")),
        city: emptyToUndefined(form.get("city")),
        industry,
        max_results: Number(form.get("max_results")) || 20,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Discovery failed unexpectedly.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Discover Businesses</h1>
        <p className="mt-1 text-sm text-gray-500">
          Finds real businesses matching a market + industry via OpenStreetMap (free,
          public data — no scraping, no private information). Leave city blank to
          search an entire state/region at once, and list multiple industries
          comma-separated (e.g. &quot;Roofing, Plumbing, Electrician&quot;) to pull
          several categories in one run. Duplicates already in your database are
          skipped automatically.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="grid grid-cols-1 gap-4 rounded-md border border-gray-200 bg-white p-6 sm:grid-cols-2"
      >
        <div>
          <label htmlFor="country" className={labelClass}>
            Country *
          </label>
          <input id="country" name="country" required className={inputClass} placeholder="USA" />
        </div>
        <div>
          <label htmlFor="region" className={labelClass}>
            Region / State
          </label>
          <input id="region" name="region" className={inputClass} placeholder="Texas" />
        </div>
        <div>
          <label htmlFor="city" className={labelClass}>
            City
          </label>
          <input id="city" name="city" className={inputClass} placeholder="Houston" />
        </div>
        <div>
          <label htmlFor="industry" className={labelClass}>
            Industry *
          </label>
          <input
            id="industry"
            name="industry"
            required
            className={inputClass}
            placeholder="Roofing  or  Roofing, Plumbing, Electrician"
          />
        </div>
        <div>
          <label htmlFor="max_results" className={labelClass}>
            Max results
          </label>
          <input
            id="max_results"
            name="max_results"
            type="number"
            min={1}
            max={200}
            defaultValue={20}
            className={inputClass}
          />
        </div>
        <div className="flex items-end sm:col-span-2">
          <button
            type="submit"
            disabled={searching}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {searching ? "Searching…" : "Discover Businesses"}
          </button>
        </div>
      </form>

      {result && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-4 rounded-md border border-gray-200 bg-white p-4 text-sm">
            <span>
              <strong>{result.found}</strong> found
            </span>
            <span>
              <strong>{result.created}</strong> added
            </span>
            <span>
              <strong>{result.skipped_duplicates}</strong> already in database
            </span>
          </div>

          {result.source_error && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              {result.source_error}
            </div>
          )}

          {!result.source_error && result.found === 0 && (
            <div className="rounded-md border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-500">
              No businesses matched that search. Try a more specific city, or an industry
              term closer to common trade names (e.g. &quot;Roofing&quot; rather than
              &quot;Home Improvement&quot;).
            </div>
          )}

          {result.businesses.length > 0 && (
            <div className="overflow-hidden rounded-md border border-gray-200 bg-white">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  <tr>
                    <th className="px-4 py-3">Name</th>
                    <th className="px-4 py-3">City</th>
                    <th className="px-4 py-3">Phone</th>
                    <th className="px-4 py-3">Website</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {result.businesses.map((b) => (
                    <tr key={b.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <Link
                          href={`/businesses/${b.id}`}
                          className="font-medium text-gray-900 hover:underline"
                        >
                          {b.name}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-gray-500">{b.city ?? "—"}</td>
                      <td className="px-4 py-3 text-gray-500">{b.phone ?? "—"}</td>
                      <td className="px-4 py-3 text-gray-500">
                        {b.submitted_website_url ? (
                          <a
                            href={b.submitted_website_url}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="text-blue-600 hover:underline"
                          >
                            visit
                          </a>
                        ) : (
                          "none"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function emptyToUndefined(value: FormDataEntryValue | null): string | undefined {
  const str = typeof value === "string" ? value.trim() : "";
  return str.length > 0 ? str : undefined;
}
