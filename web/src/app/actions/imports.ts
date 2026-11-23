'use server';

import {
  ApiService,
  type ImportDecision,
  type ImportDecisionResult,
  type ImportItem,
  type ImportSummary,
} from '@/lib/api';
import { revalidatePath } from 'next/cache';

function safeRevalidatePath(path: string) {
  try {
    revalidatePath(path);
  } catch {
    // outside a request (tests)
  }
}

const SOURCES = ['kindle', 'readwise', 'goodreads'] as const;
type Failure = { ok: false; reason: 'invalid' | 'unavailable' | 'too_large'; message?: string };

/** Sends one piece of an import file (see lib/importChunks). */
export async function importPieceAction(source: string, text: string): Promise<{ ok: true; summary: ImportSummary } | Failure> {
  if (!(SOURCES as readonly string[]).includes(source) || typeof text !== 'string' || !text.trim()) {
    return { ok: false, reason: 'invalid' };
  }
  try {
    const res = await ApiService.importPiece(source, text);
    if (res.ok) return { ok: true, summary: res.body as ImportSummary };
    if (res.status === 413) return { ok: false, reason: 'too_large' };
    if (res.status === 400) return { ok: false, reason: 'invalid', message: (res.body as { error?: string }).error };
    return { ok: false, reason: 'unavailable' };
  } catch {
    return { ok: false, reason: 'unavailable' };
  }
}

export async function getImportQueueAction(): Promise<{ items: ImportItem[]; pending: number } | null> {
  try {
    return await ApiService.getImportQueue();
  } catch {
    return null;
  }
}

export async function decideImportsAction(decision: ImportDecision): Promise<{ ok: true; result: ImportDecisionResult } | Failure> {
  if (!Array.isArray(decision?.ids) || decision.ids.length === 0 || decision.ids.length > 100) {
    return { ok: false, reason: 'invalid' };
  }
  try {
    const res = await ApiService.decideImports(decision);
    if (!res.ok) return { ok: false, reason: res.status === 400 ? 'invalid' : 'unavailable' };
    if (decision.action === 'approve') {
      safeRevalidatePath('/favorites');
      safeRevalidatePath('/learning');
    }
    return { ok: true, result: res.body as ImportDecisionResult };
  } catch {
    return { ok: false, reason: 'unavailable' };
  }
}
