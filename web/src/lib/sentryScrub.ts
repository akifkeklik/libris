/**
 * Privacy filter for Sentry events from the web app (same rules as the API's error_tracking.py).
 *
 * Libris holds reading notes, questions and e-mail addresses; none of it may reach Sentry:
 *  - no user identity; request reduced to method and path (no query string, body, cookies);
 *    only an allowlist of headers;
 *  - exception messages replaced by "[redacted]" (type and stack trace kept): they can quote user text;
 *  - breadcrumbs: no data payloads, URLs without query strings, console lines and UI text dropped;
 *  - e-mail addresses masked and long text truncated in whatever text remains.
 */

import type { Breadcrumb, ErrorEvent } from '@sentry/nextjs';

type Json = Record<string, unknown>;

const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
const ALLOWED_HEADERS = new Set(['user-agent', 'content-type', 'x-request-id']);
const MAX_TEXT = 300;

export function cleanText(value: unknown): unknown {
  if (typeof value !== 'string') return value;
  const text = value.replace(EMAIL, '[email]');
  return text.length <= MAX_TEXT ? text : `${text.slice(0, MAX_TEXT)}…[truncated]`;
}

const stripQuery = (url: unknown) => (typeof url === 'string' ? url.split('?')[0].split('#')[0] : url);

export function scrubSentryEvent<T extends object>(event: T): T {
  const e = event as unknown as Json;
  e.user = {};
  const request = e.request as Json | undefined;
  if (request && typeof request === 'object') {
    const headers = (request.headers as Record<string, string> | undefined) ?? {};
    e.request = {
      method: request.method,
      url: stripQuery(request.url),
      headers: Object.fromEntries(Object.entries(headers).filter(([k]) => ALLOWED_HEADERS.has(k.toLowerCase()))),
    };
  }
  const extra = e.extra as Json | undefined;
  e.extra = extra && 'request_id' in extra ? { request_id: extra.request_id } : {};
  if (e.logentry && typeof e.logentry === 'object') {
    e.logentry = { message: cleanText((e.logentry as Json).message) };
    delete e.message;
  } else if ('message' in e) {
    e.message = cleanText(e.message);
  }
  const values = ((e.exception as Json | undefined)?.values as Json[] | undefined) ?? [];
  for (const exc of values) {
    if (exc.value) exc.value = '[redacted]';
    const frames = ((exc.stacktrace as Json | undefined)?.frames as Json[] | undefined) ?? [];
    for (const frame of frames) delete frame.vars;
  }
  const crumbs = ((e.breadcrumbs as unknown) as Json[] | undefined) ?? [];
  if (Array.isArray(crumbs)) crumbs.forEach((c) => scrubBreadcrumb(c));
  return event;
}

export function scrubBreadcrumb<T extends object>(crumb: T): T | null {
  const c = crumb as unknown as Json;
  // Console output and UI events can contain note text or what the reader typed.
  if (c.category === 'console' || (typeof c.category === 'string' && c.category.startsWith('ui.'))) return null;
  const data = c.data as Json | undefined;
  if (data && typeof data === 'object') {
    // Keep only what describes a request, never its content.
    c.data = Object.fromEntries(
      Object.entries(data)
        .filter(([k]) => ['url', 'method', 'status_code', 'from', 'to'].includes(k))
        .map(([k, v]) => [k, k === 'url' || k === 'from' || k === 'to' ? stripQuery(v) : v]),
    );
  }
  if ('message' in c) c.message = cleanText(c.message);
  return crumb;
}

/** Options shared by the browser and server SDKs. */
export function sentryOptions(dsn: string, environment?: string) {
  return {
    dsn,
    environment: environment || 'production',
    sendDefaultPii: false,
    tracesSampleRate: 0,
    // No Session Replay: it records what is on screen, including notes.
    beforeSend: (event: ErrorEvent) => scrubSentryEvent(event),
    beforeBreadcrumb: (crumb: Breadcrumb) => scrubBreadcrumb(crumb),
  };
}
