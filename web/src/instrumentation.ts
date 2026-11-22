// Optional server-side error tracking (Server Components, Route Handlers, Server Actions).
// Off unless SENTRY_DSN is set; events pass through the same privacy filter as the browser.
import type { Instrumentation } from 'next';
import { sentryOptions } from '@/lib/sentryScrub';

const dsn = process.env.SENTRY_DSN;

export async function register() {
  if (!dsn) return;
  try {
    const Sentry = await import('@sentry/nextjs');
    Sentry.init(sentryOptions(dsn, process.env.SENTRY_ENVIRONMENT));
  } catch {
    // Monitoring must never stop the server from starting.
  }
}

export const onRequestError: Instrumentation.onRequestError = async (err, request, context) => {
  if (!dsn) return;
  try {
    const Sentry = await import('@sentry/nextjs');
    Sentry.captureRequestError(err, request, context);
  } catch {
    // ignore
  }
};
