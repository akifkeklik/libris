import { createBrowserClient, parseCookieHeader, serializeCookieHeader } from '@supabase/ssr'
import { REMEMBER_COOKIE, applyRemember, isSessionOnly } from './remember'

// Client components also render on the server, where there is no document: no cookies there.
const browserCookies = () =>
  typeof document === 'undefined' ? [] : parseCookieHeader(document.cookie)

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return browserCookies().map(({ name, value }) => ({ name, value: value ?? '' }))
        },
        setAll(cookiesToSet) {
          if (typeof document === 'undefined') return
          const sessionOnly = isSessionOnly(browserCookies().find((c) => c.name === REMEMBER_COOKIE)?.value)
          cookiesToSet.forEach(({ name, value, options }) => {
            document.cookie = serializeCookieHeader(name, value, applyRemember(options, sessionOnly))
          })
        },
      },
    },
  )
}
