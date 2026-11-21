/** Only same-site relative paths are allowed as post-auth redirects (no //host, /\host or absolute URLs). */
export function sanitizeRedirect(url: string | null): string {
  if (!url) return '/catalog';
  const trimmed = url.trim();
  // Reject protocol-relative slashes (//) or backslashes (/\)
  if (!trimmed.startsWith('/') || trimmed.startsWith('//') || trimmed.startsWith('/\\')) {
    return '/catalog';
  }
  try {
    const parsed = new URL(trimmed, 'http://localhost');
    if (parsed.origin === 'http://localhost' && parsed.pathname.startsWith('/')) {
      return parsed.pathname + parsed.search;
    }
  } catch {
    return '/catalog';
  }
  return '/catalog';
}
