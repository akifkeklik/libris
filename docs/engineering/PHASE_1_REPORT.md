# Faz 1: İlk İzlenim ve Hız

**Branch:** `feat/phase-1-first-impression` · **Durum:** kod tamamlandı ve test edildi; production adımları sizde.

## 1. Doğrulama: sorun gerçekten var mıydı?

Ölçüm, gerçek production build (`next build` + `next start`) ile yapıldı. Backend yerine, istek sayan ve "uyku modunda" her cevabı 20 sn geciktiren sahte bir sunucu kullanıldı (Render cold start benzetimi).

| Senaryo | Sonuç | Yorum |
|---|---|---|
| Daha önce açılmış katalog/kitap sayfası, backend uykuda | **200, 0,02–0,05 sn**, backend'e 0 istek | Next.js Data Cache zaten çalışıyor. `force-dynamic` bu sürümde (16.4.6) `next.revalidate`'i iptal **etmiyor**; paketle gelen dokümandaki ifadeye rağmen ölçüm bunu gösterdi. |
| Aynı sayfa, cache süresi (300 sn) dolduktan sonra, backend uykuda | **200, 0,049 sn**; arka planda 1 yenileme isteği | Stale-while-revalidate çalışıyor; kullanıcı beklemiyor. |
| **Hiç açılmamış** bir sayfa (yeni bir arama), backend uykuda | **Önce:** 10 sn sessiz iskelet, ardından İngilizce "check your connection" hatası | **Gerçek sorun:** mesaj yanıltıcıydı ve çevrilmemişti. |

**Sonuç:** Önbellek ayarına dokunmaya gerek yoktu; yanlış ayarı "düzeltmek" yerine ölçüm yapıldı. Kişiye özel veri cache'e girmiyor: katalog ve kitap fetch'leri oturum bilgisi taşımıyor (`getHeaders(true)`); bunu mevcut `cdn_cache_security` testleri koruyor. Sayfalar `cookies()` okuduğu için HTML kullanıcılar arasında paylaşılmıyor.

## 2. Yapılanlar

| Commit | Değişiklik |
|---|---|
| `4751bf0` | **SlowServerNotice:** ana sayfa, katalog ve kitap yükleme ekranlarında 4 sn sonra "Sunucu uyandırılıyor…" bilgisi (`role=status`, `aria-live=polite`). Zaman aşımında dürüst ve çevrilmiş mesaj gösteriliyor; "Tekrar dene" düğmesi mevcut aramayı ve filtreleri koruyor. 4 yeni anahtar, 6 dilde. |
| `81e4065` | **Backend Sentry** (`sentry-sdk[flask]==2.74.0`). `SENTRY_DSN` yoksa kapalı. İki katmanlı gizlilik: SDK düzeyinde `data_collection` (kullanıcı, cookie, gövde, query, frame değişkenleri kapalı) ve `before_send`/`before_breadcrumb` (exception mesajı `[redacted]`, loglarda yalnızca şablon, e-postalar maskeli). |
| `9894089` | **Web Sentry** (`@sentry/nextjs@11.11.0`). DSN yoksa tarayıcı SDK'yı **hiç indirmiyor**. Aynı gizlilik kuralları geçerli; ayrıca console ve UI breadcrumb'ları atılıyor, Session Replay yok. |

## 3. Testler (hepsi çalıştırıldı)

| Komut | Sonuç |
|---|---|
| `ruff check backend/` | ✅ |
| `pytest backend/tests/` (yeni pinlerle birebir aynı venv'de) | ✅ 1225 passed, 1 skipped, 22 deselected |
| `npm run lint` · `tsc --noEmit` · `npm run build` | ✅ |
| `npm test` | ✅ 257/257 |
| `npm run test:e2e` (yerelde, desktop + phone) | ✅ 87 passed, 3 skipped (bilinçli atlananlar), 0 failed |
| `pip-audit` / `npm audit --omit=dev` | ✅ bilinen açık yok / 0 (dev araçlarında 9 moderate bulgu var; bunlar bu değişiklikten önce de vardı) |

Bu testlerin "gerçekten bir şey yakaladığı" ayrıca kontrol edildi:
- **Gizlilik, gerçek SDK ile:** Backend'de sentry-sdk, web'de `@sentry/nextjs` yakalayan bir transport ile çalıştırıldı. Not metni, e-posta, token, cookie ve arama sorgusu payload'da **yok**. Filtreler kapatıldığında testler **başarısız** oluyor.
- **Gizlilik açığı bulundu ve kapatıldı:** INFO seviyesindeki log satırları, argümanlarıyla (not metni dahil) breadcrumb'a dönüşüyordu. Test yalnızca tam test takımında, production'daki log seviyesi ayarlandığında başarısız oldu; şimdi test bu seviyeyi kendisi ayarlıyor.
- **Tarayıcıda doğrulama:** Chromium, 390×844 boyutunda, en ve tr. Bilgi 1,5 sn'de görünmüyor, 5,5 sn'de görünüyor; ~11 sn'de çevrilmiş zaman aşımı mesajı geliyor. DSN olmayan build'de 4 sayfa ve 48 JS isteği boyunca Sentry chunk'ı indirilmedi.

## 4. Production için manuel adımlar (isteğe bağlı; Sentry hesabı gerekir)

1. sentry.io'da iki proje oluşturun: Flask (backend) ve Next.js (web).
2. **Render** → Environment: `SENTRY_DSN=<backend DSN>`. İsteğe bağlı: `SENTRY_ENVIRONMENT=production`.
3. **Vercel** → Environment Variables: `NEXT_PUBLIC_SENTRY_DSN=<web DSN>` ve `SENTRY_DSN=<web DSN>`. `NEXT_PUBLIC_` değerleri build sırasında gömüldüğü için yeniden deploy gerekir.
4. **Doğru çalıştığını nasıl anlarım:** Render loglarında `Error tracking enabled (Sentry).` görünür. Sentry'de bir test hatası görünür. Event detayında user, cookie, query string ve exception mesajı bulunmamalı (`[redacted]`).
5. **Geri alma:** DSN değişkenlerini silip yeniden deploy edin. Kod hiçbir şey göndermez.

## 5. Her zaman açık backend: maliyet önerisi (karar sizin)

Render'ın ücretsiz planı boşta kalınca uykuya geçiyor; ilk istek bir dakikayı bulabiliyor. Üç seçenek:
- **Render Starter:** ayda **7 $**, 0,5 CPU / 512 MB, uyumaz. Bugünkü ücretsiz plan da 512 MB ve backend bu bellekte çalışıyor. Taşıma gerekmez; tek tıkla plan değişikliği.
- **Google Cloud Run (min-instances=1, 1 vCPU / 1 GiB):** idle fiyatla kabaca **12–13 $/ay**. Bu, birim fiyatlardan benim hesabım; bölgeye göre değişir.
- **Fly.io shared-cpu-1x / 1 GB:** yaklaşık **6,7 $/ay** (Ekim 2026 fiyat güncellemesi; üçüncü taraf kaynaklardan, doğrudan doğrulanamadı).

Cloud Run ve Fly, Dockerfile mevcut olsa da yeni bir platform, yeni secret yönetimi ve yeni deploy hattı demek. **Önerim Render Starter:** fark aylık birkaç dolar, operasyonel risk sıfır. Faz 1'deki "sunucu uyanıyor" ekranı, karar verilene kadar dürüst bir ara çözüm.

Kaynaklar: [Render pricing](https://render.com/pricing), [Render compute plans](https://render.com/docs/compute-plans), [Cloud Run pricing](https://cloud.google.com/run/pricing), [Cloud Run min instances](https://docs.cloud.google.com/run/docs/configuring/min-instance), [Fly.io pricing](https://fly.io/docs/about/pricing/), [Fly.io 2026 pricing update](https://fly.io/pricing-update/), [Beam: Fly.io pricing explained](https://www.beam.cloud/blog/fly-io-pricing). Satın almadan önce fiyatları resmi sayfalarda kontrol edin.

## 6. Açık riskler

- Vercel'in Data Cache'i `next start`'a benzer davranıyor, ancak stale-while-revalidate davranışı **Vercel'de ölçülmedi**.
- Sentry source map yükleme (`withSentryConfig` ve auth token) eklenmedi. Stack trace'ler minified görünecek. İhtiyaç olursa token ile ayrıca eklenebilir.
- `@sentry/nextjs` lock dosyasına yaklaşık 1.500 satır ekledi. Runtime maliyeti yalnızca DSN tanımlıysa var.
