'use server';

import {
  ApiService,
  type ProductEvent,
  type PushSubscriptionInput,
  type ReminderPreferences,
  type ReminderPreferencesInput,
} from '@/lib/api';

export async function getReminderPreferencesAction(): Promise<ReminderPreferences | null> {
  try {
    return await ApiService.getReminderPreferences();
  } catch {
    return null;
  }
}

export async function saveReminderPreferencesAction(
  prefs: ReminderPreferencesInput,
): Promise<{ ok: boolean; reason?: 'invalid' | 'unavailable' }> {
  try {
    const res = await ApiService.saveReminderPreferences(prefs);
    if (res.ok) return { ok: true };
    return { ok: false, reason: res.status === 400 ? 'invalid' : 'unavailable' };
  } catch {
    return { ok: false, reason: 'unavailable' };
  }
}

export async function getPushPublicKeyAction(): Promise<string | null> {
  try {
    return await ApiService.getPushPublicKey();
  } catch {
    return null;
  }
}

export async function savePushSubscriptionAction(sub: PushSubscriptionInput): Promise<boolean> {
  try {
    return (await ApiService.savePushSubscription(sub)).ok;
  } catch {
    return false;
  }
}

export async function deletePushSubscriptionAction(endpoint: string): Promise<boolean> {
  try {
    return (await ApiService.deletePushSubscription(endpoint)).ok;
  } catch {
    return false;
  }
}

/** Fire-and-forget: an event that cannot be recorded never disturbs the reader. */
export async function recordEventAction(event: ProductEvent): Promise<void> {
  try {
    await ApiService.recordEvent(event);
  } catch {
    // ignored on purpose (logged server-side by type)
  }
}
