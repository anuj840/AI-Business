"use client";

import Link from "next/link";
import { use, useEffect, useRef, useState } from "react";
import {
  api,
  ApiError,
  type Business,
  type PipelineResult,
} from "@/lib/api";
import { OpportunityBadge, WebsiteStatusBadge, AuditItemKindBadge } from "@/components/Badge";
import { ScoreRing } from "@/components/ScoreRing";

export default function BusinessDetailPage(props: PageProps<"/businesses/[id]">) {
  const { id } = use(props.params);

  const [business, setBusiness] = useState<Business | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const unmountedRef = useRef(false);

  useEffect(() => {
    // Reset on every (re-)mount, not just once: React 18 Strict Mode (dev
    // only) mounts -> cleans up -> mounts again on startup to surface
    // exactly this kind of bug. Without resetting here, the first simulated
    // cleanup would permanently flip this to true and silently stop the
    // job-status poll loop below before it ever does anything, in dev mode.
    unmountedRef.current = false;
    return () => {
      unmountedRef.current = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const b = await api.getBusiness(id);
        if (cancelled) return;
        setBusiness(b);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
        } else {
          setError(err instanceof ApiError ? err.message : "Failed to load business.");
        }
        return;
      }

      try {
        const analysis = await api.getAnalysis(id);
        if (!cancelled) setResult(analysis);
      } catch (err) {
        // 404 here just means /analyze hasn't been run yet — not an error state.
        if (!cancelled && !(err instanceof ApiError && err.status === 404)) {
          setError(err instanceof ApiError ? err.message : "Failed to load analysis.");
        }
      }
    }

    load().finally(() => {
      if (!cancelled) setLoadingInitial(false);
    });

    return () => {
      cancelled = true;
    };
  }, [id]);

  async function handleAnalyze() {
    setAnalyzing(true);
    setError(null);
    setJobStatus("QUEUED");

    try {
      const { job_id } = await api.analyzeBusiness(id);
      await pollJob(job_id);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not start analysis. Check the backend logs."
      );
      setAnalyzing(false);
    }
  }

  async function pollJob(jobId: string) {
    const POLL_INTERVAL_MS = 3000;
    const MAX_ATTEMPTS = 200; // ~10 minutes ceiling, matches JOB_TIMEOUT_SECONDS

    for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
      if (unmountedRef.current) return;

      let job;
      try {
        job = await api.getJob(jobId);
      } catch (err) {
        if (unmountedRef.current) return;
        setError(err instanceof ApiError ? err.message : "Lost track of the analysis job.");
        setAnalyzing(false);
        return;
      }

      if (unmountedRef.current) return;
      setJobStatus(job.status);

      if (job.status === "COMPLETED") {
        try {
          const analysis = await api.getAnalysis(id);
          if (!unmountedRef.current) setResult(analysis);
        } catch (err) {
          if (!unmountedRef.current) {
            setError(err instanceof ApiError ? err.message : "Analysis completed but failed to load.");
          }
        }
        if (!unmountedRef.current) setAnalyzing(false);
        return;
      }

      if (job.status === "FAILED" || job.status === "CANCELLED") {
        setError(job.error ?? "Analysis job failed unexpectedly.");
        setAnalyzing(false);
        return;
      }

      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    }

    if (!unmountedRef.current) {
      setError("Analysis is taking much longer than expected. Check back later or retry.");
      setAnalyzing(false);
    }
  }

  async function handleApprove() {
    setApproving(true);
    try {
      await api.approveOutreachDraft(id);
      setResult((prev) =>
        prev && prev.outreach_draft
          ? { ...prev, outreach_draft: { ...prev.outreach_draft, requires_human_approval: false } }
          : prev
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to approve draft.");
    } finally {
      setApproving(false);
    }
  }

  if (notFound) {
    return (
      <div className="rounded-md border border-gray-200 bg-white p-8 text-center">
        <p className="text-gray-600">Business not found.</p>
        <Link href="/" className="mt-3 inline-block text-sm font-medium text-gray-900 underline">
          Back to dashboard
        </Link>
      </div>
    );
  }

  if (loadingInitial || !business) {
    return <div className="text-sm text-gray-500">Loading…</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/" className="text-sm text-gray-500 hover:underline">
            ← Dashboard
          </Link>
          <h1 className="mt-1 text-2xl font-semibold">{business.name}</h1>
          <p className="mt-1 text-sm text-gray-500">
            {[business.city, business.region, business.country].filter(Boolean).join(", ") ||
              "Location unknown"}
            {business.industry ? ` · ${business.industry}` : ""}
          </p>
          {business.submitted_website_url && (
            <a
              href={business.submitted_website_url}
              target="_blank"
              rel="noreferrer noopener"
              className="mt-1 inline-block text-sm text-blue-600 hover:underline"
            >
              {business.submitted_website_url}
            </a>
          )}
        </div>
        <button
          onClick={handleAnalyze}
          disabled={analyzing}
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {analyzing
            ? `${jobStatus === "QUEUED" ? "Queued…" : "Analyzing…"} (this can take a minute)`
            : result
              ? "Re-run Analysis"
              : "Run Analysis"}
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {!result && !analyzing && (
        <div className="rounded-md border border-dashed border-gray-300 bg-white p-10 text-center text-gray-500">
          No analysis yet. Click &quot;Run Analysis&quot; to crawl the website (if any), score it,
          classify the opportunity, and generate an AI audit + outreach draft.
        </div>
      )}

      {analyzing && (
        <div className="rounded-md border border-gray-200 bg-white p-10 text-center text-gray-500">
          {jobStatus === "QUEUED"
            ? "Job queued — waiting for a worker to pick it up…"
            : "Running the pipeline — crawling the site, scoring it, and calling the AI model."}
          {" "}Stay on this page; it&apos;s polling for completion. (Navigating away stops
          the polling here, though the job itself keeps running on the server.)
        </div>
      )}

      {result && (
        <div className="space-y-6">
          {/* Status row */}
          <div className="flex flex-wrap items-center gap-3 rounded-md border border-gray-200 bg-white p-4">
            <WebsiteStatusBadge status={result.website_status} />
            <OpportunityBadge type={result.opportunity.type} />
            <span className="text-sm text-gray-500">
              {result.pages_crawled} page{result.pages_crawled === 1 ? "" : "s"} crawled
            </span>
            {result.opportunity.recommended_service && (
              <span className="text-sm text-gray-500">
                Recommended: <strong>{result.opportunity.recommended_service}</strong>
              </span>
            )}
          </div>

          {/* Scores */}
          <div className="grid grid-cols-2 gap-4 rounded-md border border-gray-200 bg-white p-6 sm:grid-cols-4">
            <ScoreRing score={result.quality_score.overall} label="Website Quality" />
            <ScoreRing score={result.lead_score.overall} label="Lead Score" />
            {Object.entries(result.quality_score.categories)
              .slice(0, 2)
              .map(([category, score]) => (
                <ScoreRing key={category} score={score} label={category.replaceAll("_", " ")} />
              ))}
          </div>

          {/* Opportunity reasons */}
          <section className="rounded-md border border-gray-200 bg-white p-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              Why this opportunity?
            </h2>
            <ul className="mt-3 list-inside list-disc space-y-1 text-sm text-gray-700">
              {result.opportunity.reasons.map((reason, i) => (
                <li key={i}>{reason}</li>
              ))}
            </ul>
          </section>

          {/* Lead score reasons */}
          {result.lead_score.reasons.length > 0 && (
            <section className="rounded-md border border-gray-200 bg-white p-6">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
                Lead score breakdown
              </h2>
              <ul className="mt-3 space-y-1 text-sm text-gray-700">
                {result.lead_score.reasons.map((r, i) => (
                  <li key={i} className="flex justify-between">
                    <span>{r.label}</span>
                    <span className="font-medium text-gray-500">+{r.points}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Audit */}
          <section className="rounded-md border border-gray-200 bg-white p-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              Audit
            </h2>
            <p className="mt-2 text-sm text-gray-700">{result.audit.summary}</p>
            {!result.audit.ai_generation_succeeded && (
              <p className="mt-2 text-xs text-amber-600">
                AI-generated interpretation was unavailable for this audit — facts below are
                still verified and safe to rely on.
              </p>
            )}

            {result.audit.priority_next_steps.length > 0 && (
              <div className="mt-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                  Priority next steps
                </h3>
                <ol className="mt-2 list-inside list-decimal space-y-1 text-sm text-gray-700">
                  {result.audit.priority_next_steps.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
              </div>
            )}

            <div className="mt-5 space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                Details
              </h3>
              <div className="max-h-80 space-y-1.5 overflow-y-auto rounded-md border border-gray-100 p-3">
                {result.audit.items.map((item, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm">
                    <AuditItemKindBadge kind={item.kind} />
                    <span className="text-gray-700">
                      {item.label !== "recommendation" &&
                      item.label !== "strength" &&
                      item.label !== "weakness"
                        ? `${item.label}: `
                        : ""}
                      {String(item.value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Outreach draft */}
          {result.outreach_draft ? (
            <section className="rounded-md border border-gray-200 bg-white p-6">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
                  Outreach Draft
                </h2>
                <span
                  className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${
                    result.outreach_draft.requires_human_approval
                      ? "bg-yellow-50 text-yellow-700 ring-yellow-600/20"
                      : "bg-green-50 text-green-700 ring-green-600/20"
                  }`}
                >
                  {result.outreach_draft.requires_human_approval ? "Pending approval" : "Approved"}
                </span>
              </div>
              <p className="mt-3 text-sm font-medium text-gray-900">
                {result.outreach_draft.subject}
              </p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-gray-700">
                {result.outreach_draft.body}
              </p>
              <p className="mt-3 text-xs text-gray-400">
                No message is ever sent automatically. This draft requires explicit human
                approval before any outreach infrastructure can use it.
              </p>
              {result.outreach_draft.requires_human_approval && (
                <button
                  onClick={handleApprove}
                  disabled={approving}
                  className="mt-4 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {approving ? "Approving…" : "Approve Draft"}
                </button>
              )}
            </section>
          ) : (
            <section className="rounded-md border border-dashed border-gray-300 bg-white p-6 text-center text-sm text-gray-500">
              No outreach draft was generated — this business was classified as{" "}
              <strong>IGNORE</strong> (no clear commercial opportunity), so outreach was
              deliberately skipped.
            </section>
          )}
        </div>
      )}
    </div>
  );
}
