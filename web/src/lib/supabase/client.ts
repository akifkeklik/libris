import { createBrowserClient, parseCookieHeader, serializeCookieHeader } from '@supabase/ssr'
import { REMEMBER_COOKIE, applyRemember, isSessionOnly } from './remember'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return parseCookieHeader(document.cookie).map(({ name, value }) => ({ name, value: value ?? '' }))
        },
        setAll(cookiesToSet) {
          const sessionOnly = isSessionOnly(
            parseCookieHeader(document.cookie).find((c) => c.name === REMEMBER_COOKIE)?.value,
          )
          cookiesToSet.forEach(({ name, value, options }) => {
            document.cookie = serializeCookieHeader(name, value, applyRemember(options, sessionOnly))
          })
        },
      },
    },
  )
}
