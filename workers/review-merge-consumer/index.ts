/**
 * CF Queue consumer — triggered by messages enqueued by the push Pages Function.
 *
 * Each message carries { email, triggeredAt }.  The consumer calls the Python
 * pipeline server's POST /api/reviews/merge endpoint, which runs
 * `sync_r2.py merge-reviews` in the background.  On success the message is
 * acked; on failure it is retried up to the queue's max_retries limit.
 *
 * Required Worker secrets (set in CF dashboard or wrangler secret put):
 *   PIPELINE_URL     — base URL of the pipeline server, e.g.
 *                      https://api.arktrace.edgesentry.io
 *   PIPELINE_SECRET  — shared secret validated by the pipeline's /api/reviews/merge
 */

export interface Env {
  PIPELINE_URL: string;
  PIPELINE_SECRET: string;
}

interface MergeJob {
  email: string;
  triggeredAt: string;
}

export default {
  async queue(batch: MessageBatch<MergeJob>, env: Env): Promise<void> {
    for (const msg of batch.messages) {
      try {
        const resp = await fetch(`${env.PIPELINE_URL}/api/reviews/merge`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Pipeline-Secret": env.PIPELINE_SECRET,
          },
          body: JSON.stringify(msg.body),
        });

        if (!resp.ok) {
          const text = await resp.text().catch(() => String(resp.status));
          console.error(`[review-merge] Pipeline returned ${resp.status}: ${text}`);
          msg.retry({ delaySeconds: 30 });
        } else {
          msg.ack();
        }
      } catch (err) {
        console.error("[review-merge] Failed to reach pipeline:", err);
        msg.retry({ delaySeconds: 30 });
      }
    }
  },
};
