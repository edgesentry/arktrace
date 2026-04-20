/**
 * POST /api/reviews/push
 *
 * Accepts vessel_reviews, vessel_reviews_audit, and analyst_briefs as Parquet
 * files in a multipart FormData body, then:
 *   1. Writes them to R2 under reviews/<email>/ (per-user prefix).
 *   2. Enqueues a merge job to the CF Queue (arktrace-review-merge).
 *
 * The queue consumer (workers/review-merge-consumer/) picks up the job and
 * calls POST /api/reviews/merge on the Python pipeline server, which runs
 * `sync_r2.py merge-reviews` to produce a single reviews/merged/*.parquet and
 * patches ducklake_manifest.json so all clients detect the update on next sync.
 *
 * Auth: Cloudflare Access injects Cf-Access-Authenticated-User-Email
 * automatically.  Requests lacking the header receive 401.
 */

interface Env {
  ARKTRACE_PUBLIC: R2Bucket;
  REVIEW_MERGE_QUEUE: Queue;
}

export const onRequestPost: PagesFunction<Env> = async (ctx) => {
  const email = ctx.request.headers.get("Cf-Access-Authenticated-User-Email");
  if (!email) {
    return json({ error: "Sign in required to push changes" }, 401);
  }

  let formData: FormData;
  try {
    formData = await ctx.request.formData();
  } catch {
    return json({ error: "Invalid request body" }, 400);
  }

  const reviews = formData.get("reviews") as File | null;
  const audit   = formData.get("audit")   as File | null;
  const briefs  = formData.get("briefs")  as File | null;

  if (!reviews || !audit || !briefs) {
    return json({ error: "Missing files: expected reviews, audit, briefs" }, 400);
  }

  const prefix  = `reviews/${encodeURIComponent(email)}`;
  const now     = new Date().toISOString();
  const putOpts = { httpMetadata: { contentType: "application/octet-stream" } };

  // 1. Write per-user Parquet files to R2
  await Promise.all([
    ctx.env.ARKTRACE_PUBLIC.put(`${prefix}/reviews.parquet`, await reviews.arrayBuffer(), putOpts),
    ctx.env.ARKTRACE_PUBLIC.put(`${prefix}/audit.parquet`,   await audit.arrayBuffer(),   putOpts),
    ctx.env.ARKTRACE_PUBLIC.put(`${prefix}/briefs.parquet`,  await briefs.arrayBuffer(),  putOpts),
  ]);

  // 2. Enqueue merge job — queue consumer calls pipeline /api/reviews/merge
  ctx.waitUntil(
    ctx.env.REVIEW_MERGE_QUEUE.send({ email, triggeredAt: now })
  );

  return json({ ok: true, email, updatedAt: now }, 200);
};

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
