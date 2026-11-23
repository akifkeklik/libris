'use client';

import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';

export interface SelectOption<V extends string> {
  value: V;
  label: string;
}

interface SelectProps<V extends string> {
  value: V;
  options: SelectOption<V>[];
  onChange: (value: V) => void;
  /** Accessible name (shown to screen readers; use `labelledBy` when a visible label exists). */
  ariaLabel?: string;
  labelledBy?: string;
  id?: string;
  disabled?: boolean;
  size?: 'sm' | 'md';
  /** Stretch the trigger to its container. */
  block?: boolean;
  className?: string;
  'data-testid'?: string;
}

/**
 * Themed replacement for the native <select>, whose open list cannot be styled and clashes with
 * the dark themes. WAI-ARIA "select-only combobox" pattern: the trigger is a combobox that owns a
 * listbox; ↑/↓/Home/End move, Enter/Space choose, Esc closes, typing jumps to a matching option.
 * Opens upwards when there is not enough room below.
 */
export function Select<V extends string>({
  value, options, onChange, ariaLabel, labelledBy, id, disabled, size = 'md', block, className, ...rest
}: SelectProps<V>) {
  const autoId = useId();
  const baseId = id ?? `sel${autoId.replace(/:/g, '')}`;
  const listId = `${baseId}-list`;
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [up, setUp] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const typed = useRef({ text: '', at: 0 });

  const selectedIndex = Math.max(0, options.findIndex((o) => o.value === value));
  const selected = options[selectedIndex];

  const openList = () => {
    if (disabled) return;
    setActive(selectedIndex);
    setOpen(true);
  };
  const close = (focusTrigger = true) => {
    setOpen(false);
    if (focusTrigger) triggerRef.current?.focus();
  };
  const choose = (i: number) => {
    const opt = options[i];
    if (opt && opt.value !== value) onChange(opt.value);
    close();
  };

  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return;
    const r = triggerRef.current.getBoundingClientRect();
    const needed = Math.min(options.length * 40 + 16, 296);
    setUp(window.innerHeight - r.bottom < needed && r.top > window.innerHeight - r.bottom);
  }, [open, options.length]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) close(false);
    };
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
  }, [open]);

  useEffect(() => {
    if (open) document.getElementById(`${baseId}-opt-${active}`)?.scrollIntoView({ block: 'nearest' });
  }, [open, active, baseId]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;
    const last = options.length - 1;
    if (!open) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
        e.preventDefault();
        openList();
      }
      return;
    }
    switch (e.key) {
      case 'ArrowDown': e.preventDefault(); setActive((a) => Math.min(last, a + 1)); return;
      case 'ArrowUp': e.preventDefault(); setActive((a) => Math.max(0, a - 1)); return;
      case 'Home': e.preventDefault(); setActive(0); return;
      case 'End': e.preventDefault(); setActive(last); return;
      case 'Enter': case ' ': e.preventDefault(); choose(active); return;
      case 'Escape': e.preventDefault(); close(); return;
      case 'Tab': close(false); return;
    }
    if (e.key.length === 1 && /\S/.test(e.key)) {
      const now = Date.now();
      typed.current = { text: (now - typed.current.at < 700 ? typed.current.text : '') + e.key.toLowerCase(), at: now };
      const hit = options.findIndex((o) => o.label.toLowerCase().startsWith(typed.current.text));
      if (hit >= 0) setActive(hit);
    }
  };

  return (
    <div ref={rootRef} className={`lb-select lb-select--${size}${block ? ' lb-select--block' : ''}${className ? ` ${className}` : ''}`}>
      <button
        ref={triggerRef}
        id={baseId}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open ? `${baseId}-opt-${active}` : undefined}
        aria-label={labelledBy ? undefined : ariaLabel}
        aria-labelledby={labelledBy}
        disabled={disabled}
        className="lb-select__trigger"
        onClick={() => (open ? close() : openList())}
        onKeyDown={onKeyDown}
        data-testid={rest['data-testid']}
      >
        <span className="lb-select__value">{selected?.label}</span>
        <ChevronDown size={size === 'sm' ? 14 : 16} aria-hidden="true" className="lb-select__chevron" />
      </button>
      {open && (
        <ul id={listId} role="listbox" aria-label={ariaLabel} tabIndex={-1}
          className={`lb-select__list${up ? ' lb-select__list--up' : ''}`}>
          {options.map((o, i) => (
            <li
              key={o.value}
              id={`${baseId}-opt-${i}`}
              role="option"
              aria-selected={o.value === value}
              className={`lb-select__option${i === active ? ' is-active' : ''}`}
              onPointerEnter={() => setActive(i)}
              onPointerDown={(e) => e.preventDefault()}
              onClick={() => choose(i)}
            >
              <span>{o.label}</span>
              {o.value === value && <Check size={15} aria-hidden="true" className="lb-select__check" />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
