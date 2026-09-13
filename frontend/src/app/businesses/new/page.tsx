"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";

const inputClass =
  "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500";
const labelClass = "block text-sm font-medium text-gray-700 mb-1";

export default function NewBusinessPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    if (!name) {
      setError("Business name is required.");
      setSubmitting(false);
      return;
    }

    const payload = {
      name,
      website_url: emptyToUndefined(form.get("website_url")),
      country: emptyToUndefined(form.get("country")),
      region: emptyToUndefined(form.get("region")),
      city: emptyToUndefined(form.get("city")),
      industry: emptyToUndefined(form.get("industry")),
      phone: emptyToUndefined(form.get("phone")),
      email: emptyToUndefined(form.get("email")),
      notes: emptyToUndefined(form.get("notes")),
    };

    try {
      const business = await api.createBusiness(payload);
      router.push(`/businesses/${business.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create business.");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Add a Business</h1>
        <p className="mt-1 text-sm text-gray-500">
          Website URL is optional — leave it blank if you don&apos;t know whether this
          business has one. The pipeline will classify accordingly.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5 rounded-md border border-gray-200 bg-white p-6">
        <div>
          <label htmlFor="name" className={labelClass}>
            Business name *
          </label>
          <input id="name" name="name" required className={inputClass} placeholder="ABC Roofing" />
        </div>

        <div>
          <label htmlFor="website_url" className={labelClass}>
            Website URL
          </label>
          <input
            id="website_url"
            name="website_url"
            type="url"
            className={inputClass}
            placeholder="https://example.com"
          />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label htmlFor="country" className={labelClass}>
              Country
            </label>
            <input id="country" name="country" className={inputClass} placeholder="USA" />
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
        </div>

        <div>
          <label htmlFor="industry" className={labelClass}>
            Industry
          </label>
          <input id="industry" name="industry" className={inputClass} placeholder="Roofing" />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="phone" className={labelClass}>
              Phone
            </label>
            <input id="phone" name="phone" className={inputClass} placeholder="+1 555-0100" />
          </div>
          <div>
            <label htmlFor="email" className={labelClass}>
              Email
            </label>
            <input id="email" name="email" type="email" className={inputClass} placeholder="info@example.com" />
          </div>
        </div>

        <div>
          <label htmlFor="notes" className={labelClass}>
            Notes
          </label>
          <textarea id="notes" name="notes" rows={3} className={inputClass} />
        </div>

        <div className="flex justify-end gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Creating…" : "Create Business"}
          </button>
        </div>
      </form>
    </div>
  );
}

function emptyToUndefined(value: FormDataEntryValue | null): string | undefined {
  const str = typeof value === "string" ? value.trim() : "";
  return str.length > 0 ? str : undefined;
}
