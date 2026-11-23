'use client';

import { useEffect, useRef, useState } from 'react';
import { Flag, Loader2, MoreHorizontal, Pencil, Sparkles } from 'lucide-react';
import { usePreferences } from '@/components/PreferencesProvider';
import { Select } from '@/components/Select';
import { regenerateLearningItemAction, reportLearningItemAction, updateLearningItemAction } from '@/app/actions/learning';
import type { TranslationKey } from '@/lib/i18n';

const REASONS: { value: string; label: TranslationKey }[] = [
  { value: 'unclear', label: 'card_report_unclear' },
  { value: 'wrong', label: 'card_report_wrong' },
  { value: 'too_easy', label: 'card_report_too_easy' },
  { value: 'duplicate', label: 'card_report_duplicate' },
  { value: 'other', label: 'card_report_other' },
];

type Mode = 'idle' | 'menu' | 'edit' | 'report';

/**
 * The reader's control over one review card: edit it, ask for a new AI question, or report a bad
 * question (the card then leaves the queue). Changes apply to this card only.
 */
export function CardControls({ itemId, question, answer, onChanged, onRemoved }: {
  itemId: string;
  question: string;
  answer: string;
  onChanged: (next: { question: string; answer: string }) => void;
  onRemoved: () => void;
}) {
  const { t } = usePreferences();
  const [mode, setMode] = useState<Mode>('idle');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [draftQ, setDraftQ] = useState(question);
  const [draftA, setDraftA] = useState(answer);
  const [reason, setReason] = useState('unclear');
  const [comment, setComment] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (mode !== 'menu') return;
    const close = (e: PointerEvent) => { if (!menuRef.current?.contains(e.target as Node)) setMode('idle'); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') { setMode('idle'); triggerRef.current?.focus(); } };
    document.addEventListener('pointerdown', close);
    document.addEventListener('keydown', esc);
    menuRef.current?.querySelector<HTMLButtonElement>('[role=menuitem]')?.focus();
    return () => { document.removeEventListener('pointerdown', close); document.removeEventListener('keydown', esc); };
  }, [mode]);

  const regenerate = async () => {
    setMode('idle');
    setBusy(true);
    setMessage(null);
    const res = await regenerateLearningItemAction(itemId);
    setBusy(false);
    if (res.ok && res.question) {
      onChanged({ question: res.question, answer });
      setMessage(t('card_regenerated'));
    } else {
      setMessage(t(res.reason === 'limit' ? 'card_regenerate_limit' : 'card_regenerate_failed'));
    }
  };

  const saveEdit = async () => {
    if (!draftQ.trim() || !draftA.trim()) return;
    setBusy(true);
    const res = await updateLearningItemAction(itemId, { question: draftQ.trim(), answer: draftA.trim() });
    setBusy(false);
    if (res.success) {
      onChanged({ question: draftQ.trim(), answer: draftA.trim() });
      setMode('idle');
      setMessage(t('card_saved'));
    } else {
      setMessage(t('card_action_failed'));
    }
  };

  const sendReport = async () => {
    setBusy(true);
    const ok = await reportLearningItemAction(itemId, reason, comment);
    setBusy(false);
    if (ok) onRemoved();
    else setMessage(t('card_action_failed'));
  };

  return (
    <div className="card-controls">
      <div className="card-controls__anchor" ref={menuRef}>
        <button ref={triggerRef} type="button" className="card-controls__trigger" aria-haspopup="menu" aria-expanded={mode === 'menu'}
          aria-label={t('card_controls_label')} disabled={busy} onClick={() => setMode(mode === 'menu' ? 'idle' : 'menu')}
          data-testid={`card-controls-${itemId}`}>
          {busy ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <MoreHorizontal size={18} aria-hidden="true" />}
        </button>
        {mode === 'menu' && (
          <div role="menu" className="card-controls__menu" aria-label={t('card_controls_label')}
            onKeyDown={(e) => {
              const items = [...(menuRef.current?.querySelectorAll<HTMLButtonElement>('[role=menuitem]') ?? [])];
              const i = items.indexOf(document.activeElement as HTMLButtonElement);
              if (e.key === 'ArrowDown') { e.preventDefault(); items[(i + 1) % items.length]?.focus(); }
              if (e.key === 'ArrowUp') { e.preventDefault(); items[(i - 1 + items.length) % items.length]?.focus(); }
            }}>
            <button role="menuitem" type="button" onClick={() => { setDraftQ(question); setDraftA(answer); setMode('edit'); }}>
              <Pencil size={15} aria-hidden="true" /> {t('card_edit')}
            </button>
            <button role="menuitem" type="button" onClick={regenerate}>
              <Sparkles size={15} aria-hidden="true" /> {t('card_regenerate')}
            </button>
            <button role="menuitem" type="button" className="is-danger" onClick={() => setMode('report')}>
              <Flag size={15} aria-hidden="true" /> {t('card_report')}
            </button>
          </div>
        )}
      </div>

      {mode === 'edit' && (
        <div className="card-controls__panel" data-testid="card-edit-form">
          <label className="input-label" htmlFor={`cq-${itemId}`}>{t('question_prompt_label')}</label>
          <textarea id={`cq-${itemId}`} className="input-field" rows={2} maxLength={500} value={draftQ} onChange={(e) => setDraftQ(e.target.value)} />
          <label className="input-label" htmlFor={`ca-${itemId}`}>{t('question_answer_label')}</label>
          <textarea id={`ca-${itemId}`} className="input-field" rows={3} maxLength={5000} value={draftA} onChange={(e) => setDraftA(e.target.value)} />
          <div className="card-controls__actions">
            <button type="button" className="btn btn-primary" disabled={busy || !draftQ.trim() || !draftA.trim()} onClick={saveEdit}>{t('card_save')}</button>
            <button type="button" className="btn btn-outline" onClick={() => setMode('idle')}>{t('cancel')}</button>
          </div>
        </div>
      )}

      {mode === 'report' && (
        <div className="card-controls__panel" data-testid="card-report-form">
          <p style={{ margin: 0, fontWeight: 600 }} id={`cr-${itemId}`}>{t('card_report_title')}</p>
          <Select value={reason} onChange={setReason} labelledBy={`cr-${itemId}`} block
            options={REASONS.map((r) => ({ value: r.value, label: t(r.label) }))} />
          <label className="input-label" htmlFor={`cc-${itemId}`}>{t('card_report_comment')}</label>
          <textarea id={`cc-${itemId}`} className="input-field" rows={2} maxLength={300} value={comment} onChange={(e) => setComment(e.target.value)} />
          <p className="text-muted" style={{ fontSize: '0.8rem', margin: 0 }}>{t('card_report_effect')}</p>
          <div className="card-controls__actions">
            <button type="button" className="btn btn-primary" disabled={busy} onClick={sendReport} data-testid="card-report-submit">{t('card_report_submit')}</button>
            <button type="button" className="btn btn-outline" onClick={() => setMode('idle')}>{t('cancel')}</button>
          </div>
        </div>
      )}

      <p role="status" aria-live="polite" className="card-controls__status">{message}</p>
    </div>
  );
}
