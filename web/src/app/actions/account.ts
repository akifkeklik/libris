'use server';

import { ApiService } from '@/lib/api';

export type DeleteAccountResult = { ok: true } | { ok: false; reason: 'unavailable' | 'failed' };

/** Deletes the signed-in reader's account through the API (which uses their own session). */
export async function deleteAccountAction(): Promise<DeleteAccountResult> {
  try {
    const status = await ApiService.deleteAccount();
    if (status === 200) return { ok: true };
    return { ok: false, reason: status === 503 ? 'unavailable' : 'failed' };
  } catch (err) {
    console.warn('[deleteAccount]', err instanceof Error ? err.name : 'error');
    return { ok: false, reason: 'failed' };
  }
}

export type ExportResult = { ok: true; content: string; filename: string; mimeType: string } | { ok: false };

/** Fetches the reader's full data export (their own session) for download in the browser. */
export async function exportAccountAction(format: 'json' | 'markdown'): Promise<ExportResult> {
  try {
    const file = await ApiService.exportAccount(format === 'markdown' ? 'markdown' : 'json');
    return file ? { ok: true, ...file } : { ok: false };
  } catch (err) {
    console.warn('[exportAccount]', err instanceof Error ? err.name : 'error');
    return { ok: false };
  }
}
