# Devir belgesi

Tarih: 2026-11-24.

## Sistem
- **Web:** Next.js 16 (`web/`), Vercel. Sunucu eylemleri backend'e gider.
- **Backend:** Flask, Python 3.12 (`backend/`), Render, yalnızca main'den deploy olur. Katmanlar: `domain` → `application/use_cases` → `infrastructure`; bağlama `container.py`.
- **Veri:** Supabase (Auth, RLS, pgvector). Migration'lar `backend/scripts/NN_*.sql`, elle uygulanır.
- **Hatırlatma işçisi:** GitHub Actions, saatlik; ayrı, dar yetkili `reminder_worker` rolü.

## Fazlar ve raporlar
| Faz | Konu | Belge |
|---|---|---|
| 0 | Güven ve güvenilirlik | `PHASE_0_PRODUCTION_RUNBOOK.md` |
| 1 | İlk izlenim, hız | `PHASE_1_REPORT.md` |
| 2 | Hesap, hukuk | `PHASE_2_REPORT.md` |
| UI | Arayüz incelemesi | `UI_UX_REVIEW_REPORT.md` |
| 3 | Hatırlatma | `PHASE_3_REPORT.md` |
| 4 | İçe aktarma | `PHASE_4_REPORT.md` |
| 5 | Kart kontrolü, FSRS, Anki | `PHASE_5_REPORT.md` |

Yayın adımları tek yerde: `PRODUCTION_READINESS_CHECKLIST.md`.

## Bilmeniz gereken dersler
1. **Paylaşılan katalog tablosuna istek sırasında yazmayın.** pandas yazarken iş parçacığı güvenli değildir; bu yüzden sohbet ve öneriler çökebiliyordu (#110).
2. **"Kararsız test" demeden önce hatanın aynısını arayın.** Yukarıdaki hata iki gün "kararsız" sanıldı.
3. PostgreSQL'de `now()` bir işlem boyunca sabittir; sıralama için `clock_timestamp()`.
4. Yerel global Python'un paketleri kaymış; testleri `backend/requirements.txt` ile kurulmuş bir venv'de çalıştırın.
5. İstemci bileşenleri sunucuda da çalışır; `document` kullanmadan önce kontrol edin.

## Testler
```
ruff check backend/ && PYTHONPATH=. python -m pytest backend/tests/
cd web && npm run lint && npm test && npm run build && npx playwright test
```
SQL çalışma testleri `backend/tests/sql/`, CI'da Migration Validation işinde koşar.

## Açık işler
- Canlıya alma adımlarının tamamı (liste yukarıda).
- Kuyruk, içe aktarma ve not uçlarına dakika sınırı (`GEMINI_PRODUCTION_READINESS.md`).
- Yeni ekranlarda axe taraması; Safari, Firefox ve gerçek telefon testi.
- `product_events` için bir gösterge ekranı yok.
- AI değerlendirmesinde insan onaylı etiket yok.
- Python 3.15 yükseltmesi: bağımlılıkların hazır paketleri yok, Docker derlemesi düşüyor; paketler destekleyince yeniden denenmeli.

## Kıdemli gözüyle değerlendirme (2026-11-24)

| Alan | Durum |
|---|---|
| Güçlü | Katmanlı mimari, RLS + iki okurla SQL testi, geniş test seti, TypeScript'te `any` yok, TODO/FIXME yok, container root olmayan kullanıcıyla çalışıyor |
| Sunucu darboğazı | Çözüldü: gunicorn `gthread`, 4 thread (`WEB_THREADS`). Postgres bağlantısı thread başına, katalog değişiklikleri kilitli. Render'da başlatma komutu Dockerfile'ı eziyorsa orada da değiştirilmeli |
| Güvenlik | CSP **rapor modunda** (2026-11-26): giriş yapılmış 9 ekran × 2 boyutta ihlal 0 (archive.org kapakları eklendi). Birkaç gün canlıda ihlal görünmezse `next.config.ts`'te anahtar adı `Content-Security-Policy` yapılmalı. Model dosyası pickle: yalnızca repodaki dosya yüklenmeli |
| Bakım | Okur araçları `routes.py`'den `reader_tools.py`'ye taşındı (1.968 → 1.711 satır; 61 ucun URL haritası birebir aynı). `ai_rag.py` (1.850) hâlâ büyük; ayrı, davranış testli bir PR ister. 917 satır içi stil; 177 genel `except` |
| Repo | 11,7 MB `tfidf.pkl` git'te; derlemede üretilebilir. `backend/Procfile` Dockerfile'dan farklı bir modül yolu kullanıyor |
| Ürün | Yeni özellikler canlıda migration bekliyor; gerçek kullanıcı verisi ve insan onaylı AI etiketi yok |

Ruff'ın 122 "hardcoded SQL" uyarısı tek tek incelenmedi.

## 2026-11-26 ölçümleri

- **AI süresi (backend içinde, gerçek Gemini, 3 soru):** toplam 2,3–4,2 sn. Vektör araması 1,0–1,6 sn, Gemini 0,8–1,4 sn, soru vektörü 0,4–1,2 sn. Kullanıcının gördüğü 6–10 sn'nin kalanı Render ücretsiz katmanı ve ağ. Önce Render'da aynı ölçüm, sonra `hardening/04` (vektör RPC) değerlendirilmeli.
- **Goodreads puanı:** veri modelinde kitap başına tek durum var (raf veya beğeni), puan alanı yok. Puanı uygulamak yeni bir sütun ve kütüphane arayüzü ister; ekran metni artık puan vaat etmiyor.
- **Erişilebilirlik (giriş yapılmış ekranlar):** cevap butonları ve açılır menüde 3 kontrast hatası bulundu, düzeltildi; tekrar taramada 0.
