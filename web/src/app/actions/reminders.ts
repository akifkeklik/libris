'use server';

import { ApiService, type ReminderPreferences, type ReminderPreferencesInput } from '@/lib/api';

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
