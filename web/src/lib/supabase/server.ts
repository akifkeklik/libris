import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { assertSafeSupabaseTarget } from './isolation'
import { REMEMBER_COOKIE, applyRemember, isSessionOnly } from './remember'

let testClientOverride: ReturnType<typeof createServerClient> | null = null;

export function setTestClient(client: unknown) {
  testClientOverride = client as ReturnType<typeof createServerClient> | null;
}

export function isTestClientActive(): boolean {
  return testClientOverride !== null;
}

export async function createClient() {
  if (testClientOverride) {
    return testClientOverride;
  }

  let cookieStore: {
    getAll: () => { name: string; value: string }[];
    set: (name: string, value: string, options?: unknown) => void;
  } | Awaited<ReturnType<typeof cookies>>;
  try {
    cookieStore = await cookies();
  } catch {
    // When called outside Next.js request lifecycle (e.g. testing)
    cookieStore = {
      getAll: () => [],
      set: () => {},
    };
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

  const client = createServerClient(
    supabaseUrl,
    supabaseAnonKey,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            const sessionOnly = isSessionOnly(cookieStore.getAll().find((c) => c.name === REMEMBER_COOKIE)?.value);
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, applyRemember(options, sessionOnly))
            );
          } catch {
            // Ignored outside request lifecycle
          }
        },
      },
    }
  );

  (client as unknown as { __isRealClient?: boolean }).__isRealClient = true;

  // Wrap client.from with fail-closed isolation guard
  const originalFrom = client.from.bind(client);
  client.from = ((table: string) => {
    assertSafeSupabaseTarget(supabaseUrl, `table query: ${table}`);
    return originalFrom(table);
  }) as typeof client.from;

  return client;
}
