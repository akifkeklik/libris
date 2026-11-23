/**
 * Browser side of Web Push reminders (Faz 3). Client-only helpers; every call is guarded so a
 * browser without push support simply reports it instead of throwing.
 */
import type { PushSubscriptionInput } from '@/lib/api';

export type PushSupport = 'supported' | 'unsupported' | 'ios-needs-install' | 'denied';

export function isIos(): boolean {
  if (typeof navigator === 'undefined') return false;
  return /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

export function isStandalone(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia?.('(display-mode: standalone)').matches
    || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

export function pushSupport(): PushSupport {
  if (typeof window === 'undefined') return 'unsupported';
  const capable = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  // iOS/iPadOS (16.4+) only offers Web Push to sites added to the Home Screen.
  if (isIos() && !isStandalone()) return 'ios-needs-install';
  if (!capable) return 'unsupported';
  if (Notification.permission === 'denied') return 'denied';
  return 'supported';
}

export function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padded = (base64 + '='.repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(padded);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

async function registration(): Promise<ServiceWorkerRegistration> {
  return (await navigator.serviceWorker.getRegistration('/')) ?? navigator.serviceWorker.register('/sw.js');
}

/** Asks for permission (must run from a click) and returns the subscription to store. */
export async function subscribeToPush(publicKey: string): Promise<PushSubscriptionInput | 'denied' | null> {
  try {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return 'denied';
    const reg = await registration();
    await navigator.serviceWorker.ready;
    const sub = (await reg.pushManager.getSubscription())
      ?? (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(publicKey) }));
    const json = sub.toJSON();
    if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) return null;
    return { endpoint: json.endpoint, keys: { p256dh: json.keys.p256dh, auth: json.keys.auth } };
  } catch (err) {
    console.warn('[push] subscribe failed', (err as Error)?.name);
    return null;
  }
}

/** Removes this browser's subscription and returns its endpoint (to delete server-side). */
export async function unsubscribeFromPush(): Promise<string | null> {
  try {
    const reg = await navigator.serviceWorker.getRegistration('/');
    const sub = await reg?.pushManager.getSubscription();
    if (!sub) return null;
    const endpoint = sub.endpoint;
    await sub.unsubscribe();
    return endpoint;
  } catch {
    return null;
  }
}
