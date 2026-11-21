// Optional browser error tracking. NEXT_PUBLIC_SENTRY_DSN is inlined at build time: when it is
// unset this block is dead code and the Sentry SDK is never downloaded by the reader's browser.
import { sentryOptions } from '@/lib/sentryScrub';

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  import('@sentry/nextjs')
    .then((Sentry) => {
      Sentry.init(sentryOptions(dsn, process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT));
    })
    .catch(() => {
      // Monitoring must never break the app.
    });
}
