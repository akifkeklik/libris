'use client';

import React, { Suspense, useEffect } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useAuth } from '@/components/AuthProvider';
import { usePreferences } from '@/components/PreferencesProvider';
import { LearningDashboard } from '@/components/LearningDashboard';
import { Lock, Loader2 } from 'lucide-react';
import { recordEventAction } from '@/app/actions/reminders';

function LearningDashboardWithParams() {
  const searchParams = useSearchParams();
  const concept = searchParams.get('concept') || undefined;
  const fromReminder = searchParams.get('utm_source') === 'reminder';
  const channel = searchParams.get('reminder_channel') === 'push' ? 'push' : 'email';
  const reminderDate = searchParams.get('reminder_date') ?? '';

  useEffect(() => {
    // reminder_opened: once per reminder (date + channel) and tab, even if the page reloads.
    if (!fromReminder) return;
    const key = `libris-reminder-opened:${channel}:${reminderDate}`;
    try {
      if (sessionStorage.getItem(key)) return;
      sessionStorage.setItem(key, '1');
    } catch {
      // storage blocked: still record once for this render
    }
    const date = /^\d{4}-\d{2}-\d{2}$/.test(reminderDate) ? reminderDate : undefined;
    void recordEventAction({ event: 'reminder_opened', props: { channel, ...(date ? { reminder_date: date } : {}) } });
  }, [fromReminder, channel, reminderDate]);

  return (
    <LearningDashboard
      initialConceptFilter={concept}
    />
  );
}

export default function LearningPage() {
  const { user, loading: authLoading } = useAuth();
  const { t } = usePreferences();

  if (authLoading) {
    return (
      <div className="container mx-auto px-4 py-12 max-w-7xl animate-pulse space-y-6">
        <div className="h-10 w-64 bg-[var(--surface-raised)] rounded-xl" />
        <div className="h-96 bg-[var(--surface-raised)] rounded-2xl" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="container mx-auto px-4 py-20 max-w-md text-center space-y-6">
        <div className="w-16 h-16 rounded-full bg-[var(--accent)]/10 text-[var(--primary-strong)] mx-auto flex items-center justify-center">
          <Lock className="w-8 h-8" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-[var(--text)]">
            {t('learning_title')}
          </h1>
          <p className="text-sm text-[var(--text-secondary)]">
            {t('learning_login_required')}
          </p>
        </div>
        <div className="flex items-center justify-center gap-3">
          <Link
            href="/login?redirect=/learning"
            className="px-5 py-2.5 rounded-xl bg-[var(--primary)] text-[var(--on-primary)] text-sm font-semibold hover:opacity-90 transition shadow-sm"
          >
            {t('nav_login')}
          </Link>
          <Link
            href="/signup?redirect=/learning"
            className="px-5 py-2.5 rounded-xl bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] text-sm font-semibold hover:bg-[var(--surface-raised)] transition"
          >
            {t('nav_signup')}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      <Suspense fallback={
        <div className="p-12 text-center flex flex-col items-center justify-center gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-[var(--primary-strong)]" />
          <p className="text-sm text-[var(--text-secondary)]">{t('learning_loading')}</p>
        </div>
      }>
        <LearningDashboardWithParams />
      </Suspense>
    </div>
  );
}
