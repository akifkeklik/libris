/**
 * Splits an import file into pieces small enough for one request (server actions accept 1 MB),
 * cutting only between entries so no highlight is torn apart:
 *  - Kindle clippings: after a "==========" separator line;
 *  - CSV (Readwise, Goodreads): between records, never inside a quoted field (quoted fields may
 *    span lines), with the header row repeated at the top of every piece.
 * The server de-duplicates by content hash, so a retried piece never creates doubles.
 */
export type ImportSource = 'kindle' | 'readwise' | 'goodreads';

export const MAX_FILE_BYTES = 4 * 1024 * 1024;
export const CHUNK_CHARS = 700_000; // UTF-8 can be up to ~1.3x larger in bytes; stays under 1 MB

export function splitImport(source: ImportSource, text: string, limit = CHUNK_CHARS): string[] {
  const clean = text.replace(/^﻿/, '').replace(/\r\n?/g, '\n');
  if (clean.length <= limit) return [clean];
  return source === 'kindle' ? splitKindle(clean, limit) : splitCsv(clean, limit);
}

function splitKindle(text: string, limit: number): string[] {
  const entries = text.split(/(?<=\n?={5,}[ \t]*\n)/);
  return pack(entries, limit, '');
}

function splitCsv(text: string, limit: number): string[] {
  const lines = text.replace(/\n$/, '').split('\n');
  const records: string[] = [];
  let current = '';
  let inQuotes = false;
  for (const line of lines) {
    current = current ? `${current}\n${line}` : line;
    // Every '"' toggles the quoted state; an escaped quote ("") toggles twice.
    for (const ch of line) if (ch === '"') inQuotes = !inQuotes;
    if (!inQuotes) {
      records.push(current + '\n');
      current = '';
    }
  }
  if (current) records.push(current + '\n');
  const [header, ...rows] = records;
  return pack(rows, limit - header.length, header);
}

function pack(parts: string[], limit: number, prefix: string): string[] {
  const out: string[] = [];
  let buf = '';
  for (const p of parts) {
    if (buf && buf.length + p.length > limit) {
      out.push(prefix + buf);
      buf = '';
    }
    buf += p; // a single entry larger than the limit still travels alone (the server rejects it clearly)
  }
  if (buf.trim()) out.push(prefix + buf);
  return out;
}

/** Guess the source from the file name and its first line, so the reader rarely has to choose. */
export function detectSource(fileName: string, head: string): ImportSource | null {
  const first = head.replace(/^﻿/, '').split(/\r?\n/, 1)[0].toLowerCase();
  if (first.includes('exclusive shelf')) return 'goodreads';
  if (first.startsWith('highlight,') || first.includes('book title')) return 'readwise';
  if (/clippings/i.test(fileName) || /\n={5,}\s*(\n|$)/.test(head)) return 'kindle';
  return null;
}
