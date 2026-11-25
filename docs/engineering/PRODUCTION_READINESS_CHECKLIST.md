# Canlıya hazırlık listesi

Tarih: 2026-11-24. İşaretsiz her satır **yapılmadı veya doğrulanmadı** demektir.

## A. Hazır
- [x] Kod main'de, CI yeşil
- [x] Migration 16–20 CI'da gerçek PostgreSQL'de uygulanıyor; 17–20 için çalışma testleri var
- [x] Geri alma betikleri: 16, 18, 19, 20 (17'nin komutları Faz 3 raporunda)
- [x] Hata takibi (Sentry) kodda; DSN verilince çalışır, kullanıcı metni temizlenir

## B. Veritabanı (sırayla; önce yedek alın)
- [x] 1. `hardening/01c_DRAFT_catalog_write_lockdown.sql` — **2026-11-25'te sahibinin onayıyla uygulandı** ve doğrulandı (anonim yazma 42501 ile reddediliyor, 6.446 kitap aynı). Geri alma betiği hazır
- [ ] 2. `hardening/04_DRAFT_harden_vector_rpcs.sql` (runbook Adım 4; `04_phase3_hybrid.sql` **değil**)
- [ ] 3. `09`, `10`, `13`
- [ ] 4. `16_account_deletion`
- [ ] 5. `17_reminders`, 6. `18_push_and_events`
- [ ] 7. `19_import_queue`, 8. `20_learning_settings`

**Kolay yol:** 3–8. adımlar tek dosyada: `backend/scripts/ops/production_rollout.sql`. SQL Editor'a yapıştırıp çalıştırın; `ROLLOUT OK` yazmalı, hata olursa hiçbir şey kaydedilmez.

Bunlar uygulanana kadar not, tekrar kartı, hatırlatma, içe aktarma ve hesap silme canlıda çalışmaz ya da "şu anda kullanılamıyor" der.

## C. Render
- [ ] `LLM_API_KEY` silindi
- [ ] `DATABASE_URL` kontrol edildi (`RENDER_DATABASE_SECURITY_AUDIT.md`)
- [ ] `APP_URL` eklendi
- [ ] İsteğe bağlı: `VAPID_PUBLIC_KEY`, `FSRS_ENABLED`, `SENTRY_DSN`

## D. GitHub Actions gizli anahtarları (hatırlatma)
- [ ] `REMINDER_DB_URL`, `RESEND_API_KEY`, `REMINDER_FROM`, `APP_URL`, `API_URL`
- [ ] İsteğe bağlı: `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`
- [ ] `ALTER ROLE reminder_worker LOGIN PASSWORD …`
- [ ] "Review Reminders" bir kez `dry_run = true` ile çalıştırıldı
- [ ] **Saatlik dış zamanlayıcı kuruldu.** GitHub zamanlaması ölçümde 31 saatte 4 kez çalıştı → `backend/scripts/ops/reminder_scheduler.sql`

## E. Giriş ve hukuk
- [ ] Google girişi: Supabase sağlayıcısı + `NEXT_PUBLIC_AUTH_GOOGLE_ENABLED`
- [ ] Supabase yönlendirme adresleri (`/auth/callback`, `/reset-password`)
- [ ] Gizlilik metnindeki köşeli parantezli boşluklar dolduruldu, hukukçu baktı

## F. Yayın sonrası
- [ ] `/api/health` ve `/api/health/ready` 200
- [ ] Test hesabı: kayıt → not → tekrar → içe aktarma → dışa aktarma → hesap silme
- [ ] Elle QA listesi (`FRONTEND_MANUAL_QA_REPORT.md`)

**Geri alma:** Render/Vercel'de önceki deploy'a dönün; hatırlatmayı Actions'tan kapatın; gerekiyorsa `scripts/rollbacks/`.
