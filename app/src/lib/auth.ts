const PRIVATE_MANIFEST_URL = import.meta.env.VITE_PRIVATE_MANIFEST_URL as string | undefined;

/** True when a private manifest URL is configured in the build. */
export const isPrivateModeEnabled = (): boolean => Boolean(PRIVATE_MANIFEST_URL);

/**
 * Check whether the user is authenticated with Cloudflare Access by probing
 * the private manifest with credentials. Returns true if the request succeeds
 * (Access cookie present), false if redirected to login or blocked.
 */
export async function checkPrivateAuth(): Promise<boolean> {
  if (!PRIVATE_MANIFEST_URL) return false;
  try {
    const resp = await fetch(PRIVATE_MANIFEST_URL, {
      method: "HEAD",
      credentials: "include",
    });
    return resp.ok;
  } catch {
    return false;
  }
}

/** Redirect to Cloudflare Access login, returning to the current page after. */
export function loginWithCFAccess(): void {
  const origin = new URL(PRIVATE_MANIFEST_URL!).origin;
  window.location.href = `${origin}/cdn-cgi/access/login?redirect_url=${encodeURIComponent(window.location.href)}`;
}

/** Redirect to Cloudflare Access logout. */
export function logoutFromCFAccess(): void {
  const origin = new URL(PRIVATE_MANIFEST_URL!).origin;
  window.location.href = `${origin}/cdn-cgi/access/logout`;
}
