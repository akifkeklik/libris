# Libris: Mühendislik Denetim Raporu

**Tarih:** 2026-11-21 · **Branch:** `ai-subsystem-audit` · **PR:** #95 (açık, merge edilmedi) · **Başlangıç commit'i:** `795ca3c`

Bu rapordaki her bulgu ya çalıştırılarak (test, script, salt-okunur sorgu) ya da kod okunarak doğrulandı; hangisi olduğu her maddede yazılıdır. Hiçbir secret değeri rapora, loglara veya commit'lere yazılmadı. Production veritabanına yalnızca `SET TRANSACTION READ ONLY` oturumlarında SELECT sorguları gönderildi; migration, yazma, deploy, merge veya force push yapılmadı.

---

## 1. Executive Summary

**Başlangıç durumu.** PR #95'in CI'ı kırmızıydı (`test_ranking_and_scores_are_unchanged` üç senaryoda). Bu adım başarısız olunca sonraki "Fast Pytest Suite" adımı atlandığından, yeni eklenen `test_catalog_write_boundary.py` CI'da hiç çalışmamıştı. Production'da sohbet (LLM) 401 ile düşüyordu; embedding çalışıyordu.

**Bitiş durumu.** CI'daki 9 işin tamamı yeşil (bölüm 6; yeni Python bağımlılık denetimi işi dahil), katalog sınır testleri CI'da çalışıyor (19/19). Sekiz küçük ve ayrı commit ile şunlar yapıldı:

1. **MMR tie-break kararsızlığı** (CI hatasının gerçek nedeni) kanıtlandı ve deterministik hale getirildi; öneri metrikleri değişmedi (önce/sonra birebir aynı).
2. **Production sohbet 401'inin kök nedeni** bulundu: sohbet ve embedding API anahtarını *zıt önceliklerle* çözüyordu. Tek bir kural getirildi; LLM hataları artık sınıflandırılıp `metrics.llm_error` ile raporlanıyor.
3. Backend: sınırsız istek gövdesi (3 MiB kabul ediliyordu) 1 MiB ile sınırlandı; 413/400/415 hatalarının 500 olarak dönmesi düzeltildi; `X-Request-Id` doğrulaması eklendi; production'daki aktivite kaydı hatasının (RLS 42501) nedeni yerelde yeniden üretilip kod tarafında giderildi.
4. Güvenlik: Flask-Cors 4.0.2'deki 3 CVE ve pytest'teki 1 CVE giderildi; CORS sözleşme testleri ve CI'a Python bağımlılık denetimi eklendi.
5. Frontend: CI'daki tek flaky E2E testinin nedeni bulunup düzeltildi.

**Açık kalan en kritik risk (kod dışı).** Production veritabanında `books` tablosu, herkese açık anon anahtarıyla **herkes tarafından INSERT ve UPDATE edilebilir durumda** (bölüm 5.3). Bunu kapatan 01c migration'ı hazır ve CI'da doğrulanıyor, fakat production'a uygulanması kullanıcı onayı gerektirir; uygulanmadı.

---

## 2. AI / RAG

### 2.1 Tespit edilen sorunlar ve yapılan değişiklikler

| # | Bulgu | Kanıt | Değişiklik | Commit |
|---|---|---|---|---|
| A1 | MMR aday sıralaması `np.argsort` (kararsız) ile yapılıyordu. Eşit skorlu kitapların sırası CPU'ya göre değişiyordu: numpy 1.26, AVX-512 olan makinelerde (GitHub runner) farklı bir sort çekirdeği kullanıyor. | Eşit skorlar bit düzeyinde eşit (`0.25` satır 0, 1, 4'te). Yalnızca argsort'un eşitlik sırası permüte edildiğinde CI'daki çıktılar birebir üretildi. Yerel makinede AVX-512 yok. | Adaylar `np.lexsort` ile önce skora, sonra normalize ISBN'e göre (ikisi de azalan) sıralanıyor; ISBN anahtarı katalog frame'i başına cache'leniyor. Satır sırası yerine ISBN kullanılmasının nedeni, `add_book`'un çalışma anında satır eklemesi. Aynı sorun `lexical_search`'te de vardı ve düzeltildi. Skor hesabı, MMR formülü ve λ değişmedi. | `d193d4f` |
| A2 | Sohbet anahtarı `LLM_API_KEY or GEMINI_API_KEY`, embedding anahtarı `GEMINI_API_KEY or LLM_API_KEY` olarak çözülüyordu. İkisi de tanımlı ve `LLM_API_KEY` eskiyse embedding çalışır, sohbet 401 alır. Production'daki durum tam olarak bu. | Kod okuma (`config.py:37`, `embedding_service.py:34`) ve mutasyon testi: eski önceliği geri koymak olay senaryosunu kırıyor. | `resolve_gemini_api_key` / `resolve_llm_api_key`: gemini sağlayıcısında `GEMINI_API_KEY` önce gelir, `LLM_API_KEY` eski ad olarak yedektir. Embedding aynı fonksiyonu kullanıyor. OpenAI sağlayıcısına hiçbir zaman Gemini anahtarı gönderilmiyor. İki anahtar tanımlı ve farklıysa açılışta (yalnızca değişken adlarıyla) uyarı veriliyor. | `1ef6eea` |
| A3 | LLM adaptörü her hatayı (`401`, `429`, timeout) sessizce `None`'a çeviriyordu. Fallback cevapta "neden" bilgisi yoktu; production'daki 401 loglarda 429'dan ayırt edilemiyordu. | Kod okuma. | Hatalar `auth`, `rate_limited`, `provider_unavailable`, `bad_request`, `timeout`, `network`, `empty_response` ve `not_configured` olarak sınıflandırılıyor. Sonuç thread-local tutuluyor (paylaşılan adaptörde her istek kendi sonucunu okur). RAG fallback'i `metrics.llm_error` alanını taşıyor; bu alan ek niteliktedir, `status`/`source`/no-cache kuralı değişmedi. | `1ef6eea` |
| A4 | A2 değişikliği `backfill_embeddings.py`'yi bozdu: script `backend/`'i `sys.path`'e ekleyip `services.embedding_service`'i top-level paket olarak import ediyor. | `backfill_embeddings.py --check` çalıştırılınca bulundu; CI'da bunu yakalayan bir test yoktu. | Modülün mevcut "önce göreli, olmazsa top-level" import deseni kullanıldı; script'in import yolunu taklit eden bir subprocess testi eklendi. | `7921add` |

**Fallback dürüstlüğü (değişiklik gerekmedi; doğrulandı).** `llm_fallback` cevapları `metrics.source = grounded_fallback` taşıyor ve cache'lenmiyor. Context dışı bir ISBN'e atıf yapan LLM cevabı reddedilip fallback'e düşüyor. Web istemcisi yalnızca `status=success` ve `source=rag_llm` olan cevabı "Gemini" olarak etiketliyor (`web/src/lib/ai_chat.ts:33`). Degraded retrieval ayrıca işaretleniyor. Testler: `test_rag_degraded_status.py`, `test_rag_grounding.py`, `ai_chat_ui.test.ts`.

### 2.2 Gemini entegrasyonunun durumu

| Konu | Durum |
|---|---|
| `LLM_PROVIDER` | Yerel `.env`: tanımlı. Production (Render): görülemedi. |
| Anahtar kullanımı | Yerelde yalnızca `GEMINI_API_KEY` var (çakışma yok). Production'da iki anahtar tanımlı, `LLM_API_KEY` eski (önceki oturum notu). |
| Production sohbet 401 | **Kod düzeltmesi bu branch'te; henüz deploy edilmedi.** Deploy beklemeden hemen çözüm: Render'da `LLM_API_KEY`'i silmek veya yeni anahtarla güncellemek (bkz. bölüm 8). |
| Secret'lar loglarda | Anahtar header'da gönderiliyor (URL'de değil); hata metinleri `_sanitize_secret` ile temizleniyor; test: log kaydında anahtar değeri yok. |
| Retry/timeout | 429/503'te 2 sn bekleyip 1 retry. `timeout=15.0` `requests`'te soket okuma süresidir, toplam süre değildir; en kötü durumda yaklaşık 32 sn. |

### 2.3 Embedding verileri (salt-okunur sorgu ile yeniden doğrulandı)

| Ölçüt | Beklenen (görev) | Ölçülen |
|---|---|---|
| Embedding sayısı | ~6.446 | **6.446** |
| Null embedding | 0 | **0** |
| Boyut | 3.072 | **3.072** (min = max) |
| Model sürümü | `models/gemini-embedding-2` | **tek sürüm, 6.446 satır** |
| Embedding'i olmayan kitap | – | **0** (6.446 kitap) |
| Kitabı olmayan (öksüz) embedding | – | **0** |
| Bayat embedding (`backfill_embeddings.py --check`, yazma yok, Gemini çağrısı yok) | – | **6.446 güncel, 0 yeniden embed gerekli** |

**Backfill yapılmadı, çünkü gerek yok.**

### 2.4 Retrieval kalitesi: önce/sonra metrikleri (offline, Gemini çağrısı yok)

Tie-break değişikliğinin (A1) etkisi, mevcut iki offline harness'la eski ve yeni kod üzerinde ölçüldü:

| Harness | Kapsam | Eski kod (`795ca3c`) ile yeni kod |
|---|---|---|
| `run_retrieval_evaluation evaluate` | seed → item (50 seed), query → item (72 sorgu), 25 sistem | **Birebir aynı** (zaman damgaları hariç JSON eşit) |
| `run_ranking_comparison --pool 100` | RAG sıralama stratejileri, aynı adaylar | **Birebir aynı** |

Commit'li `retrieval_evaluation.md` mevcut kodla birebir yeniden üretildi. `ranking_comparison.json`'da `production` sistemi aynı (rule_derived nDCG@5 0.941, proposed 0.41); diğer sistem adları script geliştikçe değişmiş.

Mevcut ölçümler (raporlardan, yeniden üretilebilir):

| Görev | Sistem | nDCG@5 | P@5 | Not |
|---|---|---|---|---|
| Seed → item | Production (TF-IDF + popülerlik + MMR λ 0.85) | 0.570 | 0.576 | MMR kapalı 0.602; MMR, +6 puanlık yazar çeşitliliği için kabul edilmiş bir takas |
| RAG, rule_derived (16 sorgu) | Production, unseeded sorguda MMR yok | 0.979 | 0.475 | Recall@5 0.975, MRR 1.0 |
| RAG, proposed etiketler (20 sorgu) | Production | 0.41–0.60 | – | Yalnızca yönlendirme amaçlı |

**Etiketlerin geçerliliği (açıkça):** Retrieval yargılarının 1.184/1.184'ü sağlayıcı bir LLM tarafından otomatik verilmiş geçici etiketlerdir; **insan tarafından doğrulanmış etiket sayısı: 0.** `rule_derived` etiketler kimlik kurallarıyla (yazar/başlık) türetilmiştir. Ayarlar aynı etiketler üzerinde seçildiği için bu sayılar genelleme ölçümü değil, yön göstergesidir (`backend/evaluation/README.md`).

**Canlı gecikme (2026-11-21'deki son canlı koşu, 44 sorgu):**

| Aşama | p50 | p95 | max |
|---|---|---|---|
| Query embedding | 429 ms | 595 ms | 1.227 ms |
| Vector RPC | 502 ms | 1.388 ms | 1.733 ms |
| Gemini generation | 5.233 ms | 15.004 ms | 23.907 ms |
| Uçtan uca, soğuk | 6.750 ms | 16.295 ms | 25.828 ms |
| Uçtan uca, cache | 0,5 ms | 0,8 ms | – |

HTTP: generate 59 deneme, 5 başarısız (4× 503, 1× ReadTimeout); embed 55/55 başarılı.

### 2.5 120 sorguluk canlı değerlendirme: maliyet tahmini (onay bekliyor; çalıştırılmadı)

Set 120 sorgudan oluşuyor (44 temel + 76 genişleme, TR/EN, 11 kategori; `test_rag_eval_expansion.py` en az 100 sorgu ve en az 10 kategoriyi zorunlu kılıyor). 76 genişleme sorgusunun önbelleğe alınmış query vektörü yok, yani hiç canlı koşulmadı.

| Kalem | Tahmin (son koşunun ölçülen oranlarından) |
|---|---|
| Embed çağrısı | ~135 (120 sorgu + adversarial set) |
| Generate çağrısı | ~150 (retry'lar dahil, ~%8) |
| **Toplam HTTP çağrısı** | **~285** |
| Generate token | ~190k (çağrı başına ~1.09k prompt + ~216 çıktı) |
| Süre | ~20–30 dk (`--pause 1.0`, p50 6,7 sn/sorgu) |

Ücret, Gemini planına bağlı olduğu için tahmin edilmedi. Ücretsiz katmanda sorun para değil RPM/RPD limitleridir, ve bu anahtar production ile paylaşılıyor. Komut: `python -m backend.scripts.run_rag_quality_eval run` (salt-okunur; veritabanına yazmaz).

### 2.6 AI test sonuçları

Bölüm 6'da. Yeni testler: tie-order ve satır-sırası bağımsızlığı (eski kodda tam olarak CI'daki üç senaryoda başarısız), anahtar çözümleme matrisi, hata kategorileri, thread izolasyonu, logda anahtar olmaması, sahte 401 oturumu üzerinden gerçek `GeminiRestClient` ile uçtan uca RAG fallback'i, script import yolu.

### 2.7 Doğrulanamayanlar

- Production sohbetinin düzeldiği (deploy edilmedi).
- Gerçek Gemini kotası ve faturalama.
- 76 genişleme sorgusunun canlı metrikleri.
- İnsan tarafından doğrulanmış kalite.

---

## 3. Backend

### 3.1 Değişiklikler

| # | Bulgu | Kanıt | Değişiklik | Commit |
|---|---|---|---|---|
| B1 | `MAX_CONTENT_LENGTH` tanımlı değildi. 3 MiB'lık bir JSON gövdesi `/api/ai/chat`'te tamamen okunup parse ediliyor ve 200 dönüyordu (1.000 karakter sınırı parse'tan sonra kontrol ediliyordu). | Test client ile ölçüldü. | `MAX_REQUEST_BYTES` (varsayılan 1 MiB, env ile ayarlanabilir). En büyük meşru gövde (learning item) ~41 KB. | `60f01a1` |
| B2 | `errorhandler(Exception)` werkzeug `HTTPException`'larını da yakalıyordu; 413/400/415 cevapları "500 Internal server error" olarak dönüp ERROR seviyesinde loglanıyordu. | Ölçüldü: limit varken 413 → 500. | `HTTPException` handler gerçek durum kodunu JSON olarak döndürüyor. 404/405 mesajları ve `request_id` içeren 500 gövdesi aynı kaldı. Kimlik doğrulama gövde okunmadan önce çalışıyor (test). | `60f01a1` |
| B3 | İstemcinin `X-Request-Id`'si uzunluk veya karakter sınırı olmadan her log satırına ve cevap header'ına kopyalanıyordu. | Kod okuma. | Yalnızca `[A-Za-z0-9._:-]{1,128}` kabul ediliyor; aksi halde yeni bir uuid4 üretiliyor. | `5fe6fde` |
| B4 | Production'da her aktivite kaydı 42501 ile düşüyordu. `user_activities` tablosunda script 08'deki INSERT politikası var ama SELECT politikası yok. supabase-py varsayılan olarak `return=representation` kullanıyor; bu da `INSERT … RETURNING` demek, ve RLS bunu reddediyor. | Production salt-okunur incelendi; yerel PostgreSQL'de (pgserver) yeniden üretildi: `RETURNING` → 42501, düz INSERT → OK, SELECT politikası eklenince → OK. | `insert(..., returning=minimal)`; dönen satır zaten kullanılmıyordu. DB değişikliği gerekmez. | `75081ba` |

### 3.2 İncelendi; değişiklik gerekmedi

- **Kimlik doğrulama:** API anahtarı `hmac.compare_digest` ile karşılaştırılıyor; eksik `LIBRIS_API_KEY` JWT doğrulamasını devre dışı bırakmıyor; geçersiz Bearer → 401. Production guard'ı DEBUG/TESTING, varsayılan secret'lar ve wildcard origin ile açılışı reddediyor.
- **Yetkilendirme:** 46 route'un tamamında yazma işlemleri `require_auth` gerektiriyor; AI uçlarında `rate_limit_ai` var. `POST /books` katalog katkısının RPC'de günlük kullanıcı limiti var (`15_reader_catalog_contributions.sql:77`).
- **SQL injection:** Dinamik SQL yalnızca sabit parçaları `%s` parametreleriyle birleştiriyor; f-string/format ile kurulan SQL yok. Küçük not: not aramasında kullanıcının yazdığı `%`/`_` ILIKE'ta escape edilmiyor (yalnızca kendi notları; güvenlik sorunu değil).
- **N+1:** Persistence katmanında döngü içinde sorgu bulunmadı; katalog 1.000'lik sayfalarla yükleniyor.

### 3.3 Mimari notlar (belgelendi, değiştirilmedi)

- **Doğrudan Postgres yolu RLS'i atlar.** `DATABASE_URL` tanımlıysa kullanıcı verisi doğrudan bağlantıyla okunuyor ve izolasyon yalnızca uygulamadaki `WHERE user_id = %s` ile sağlanıyor. Docker stack'i için tasarlanmış; Render'da `DATABASE_URL` tanımlı mı, **görülemedi**.
- Postgres adaptörleri repository başına tek bağlantı tutuyor, `connect_timeout` yok; kopan bağlantı bir istek başarısız olduktan sonra yeniden kuruluyor.
- Gunicorn: 1 sync worker, `--timeout 120`. Gemini p95 15 sn olduğundan, uzun bir sohbet isteği o sürede diğer istekleri bekletir.
- Gözlemlenebilirlik: her istek için JSON log (`request_id`, `duration_ms`), `/api/health` (liveness) ve `/api/health/ready` (DB readiness) var. Metrics endpoint'i ve hata izleme servisi yok; yeni servis eklenmedi.

---

## 4. Frontend

| Kontrol | Sonuç | Yöntem |
|---|---|---|
| Lint (`eslint`) | Geçti | Yerelde |
| Typecheck (`tsc --noEmit`) | Geçti | Yerelde |
| Unit (`tsx --test`) | 248/248 | Yerelde |
| Build (`next build`, Next 16.4.6) | Geçti, 12 route | Yerelde |
| Playwright E2E (desktop + phone) | Bölüm 6 | CI |
| Headless Chrome Visual QA | Geçti | CI |
| Vercel Preview | Status check SUCCESS (build) | PR check; preview backend yok, fonksiyonel doğrulama yapılmadı |

**Düzeltilen:** `core-journeys.spec.ts`'teki "a missing book can be added" testi CI'da flaky işaretlenmişti. Neden: route `catalog/loading.tsx` arkasında stream ediliyor, bu yüzden DOM'da kısa bir an ipucunun gizli bir kopyası daha bulunuyor ve kapsamsız `getByText` strict mode'da düşüyor. Metin kaynakta tek kez render ediliyor. Test artık kullanıcının gördüğü kopyayı doğruluyor (`7231772`).

**İncelendi; değişiklik gerekmedi:**
- Tüm `<img>` etiketlerinde `alt` var; dekoratif küçük resim `alt=""` kullanıyor.
- Grid kapakları `loading="lazy"`; detay sayfasındaki LCP kapağı eager yükleniyor (doğru).
- AI cevap kaynağı dürüstçe etiketleniyor (2.1).

**Yapılmadı:** Gerçek cihazlarda manuel görsel/responsive inceleme ve ekran okuyucu testi yapılmadı. Responsive kanıt yalnızca CI'daki phone/desktop Playwright projeleri ve Visual QA ekran görüntüleridir. Kanıta dayalı bir tasarım sorunu bulunmadığı için UI değişikliği yapılmadı.

---

## 5. Security & Infrastructure

### 5.1 Bağımlılıklar

`pip-audit` 2.10.1, izole bir venv'de çalıştırıldı:

| Paket | Sürüm | Advisory | Uygulanabilirlik | Aksiyon |
|---|---|---|---|---|
| Flask-Cors | 4.0.2 | CVE-2024-6866, CVE-2024-6844, CVE-2024-6839 | Düşük: hepsi path bazlı `resources` eşleşmesiyle ilgili, Libris ise tüm yollar için tek politika kullanıyor | 6.0.5 |
| (aynı) | 4.0.2 | (CVE değil) `allow_private_network` varsayılanı True, `Access-Control-Allow-Private-Network: true` veriyordu | Düşük | Açıkça `False` |
| pytest | 8.4.2 | CVE-2025-71176 (çok kullanıcılı UNIX'te `/tmp/pytest-of-{user}`) | Düşük, yalnızca geliştirme | 9.0.3 |

Ek olarak: `Vary: Origin` tek origin yapılandırmasında gönderilmiyordu, oysa `/api/books` herkese açık şekilde cache'lenebiliyor; artık gönderiliyor. CORS'u kapsayan hiçbir test yoktu; `test_cors_contract.py` eklendi. CI'a "Backend Dependency Security Audit" işi eklendi. npm audit (production ve tüm bağımlılıklar) CI'da zaten geçiyor.

### 5.2 Secret taraması

- Takip edilen dosyalarda ve **tüm git geçmişindeki 3.429 nesnede** gerçek `GEMINI_API_KEY`, `SUPABASE_ANON_KEY` ve DB parolası **bulunmadı** (repo PUBLIC).
- Desen eşleşmelerinin hepsi placeholder (`postgres`, `[YOUR_…]`, redaction test fixture'ları).
- Yerel `.env`'deki `GOOGLE_BOOKS_API_KEY`, `.env.example`'daki placeholder ile aynı; yerelde Google Books zenginleştirmesi kapalı.
- Yerel `.env`'deki `LIBRIS_API_KEY`/`SECRET_KEY` bilinen dev değerleri; production guard bunlarla açılmayı reddediyor.

### 5.3 Supabase: production katalog yazma yetkileri (KRİTİK; salt-okunur doğrulandı)

`verify_01c_catalog_write_lockdown.sql` production'da read-only oturumda çalıştırıldı: **58 kontrolden 33'ü FAIL, 1'i WARN.**

| Tablo | RLS | Yazma politikaları | Etki (`anon` = web bundle'daki public anahtar) |
|---|---|---|---|
| `books` | Açık (FORCE değil) | `python_ekleme_izni`: INSERT `WITH CHECK true`; `python_guncelleme_izni`: UPDATE `USING true`; roller: `public` | **İnternetteki herkes kitap ekleyebilir ve var olan her kitabı değiştirebilir.** DELETE politikası yok, bu yüzden silme engelli; TRUNCATE yetkisi yok. |
| `book_embeddings` | Açık | Yalnızca SELECT | Yetkiler verilmiş, ama RLS yazmayı engelliyor. |

- **AI etkisi:** Kitap açıklamaları LLM context'ine giriyor. Değiştirilebilen açıklama, RAG cevaplarına prompt injection yolu açar (cevaplar ISBN-grounding ile korunuyor, ama metin içeriği korunmuyor).
- **Kanıt sınırı:** Bu sonuç yetkiler ve politika semantiğinden çıkarıldı; production'a yazma denemesi **yapılmadı**.
- **Kurcalama izi bulunmadı:** 2026-10-03'ten sonra eklenen satır yok, `added_at` her satırda boş, ve 6.446 kitabın güncel metni embed edildiği hash ile eşleşiyor (embedding sonrası metin değişikliği yok). Embedding öncesi değişiklikler veya embed edilmeyen sütunlar bu kontrolle dışlanamaz.
- **Çözüm hazır:** `01c_DRAFT_catalog_write_lockdown.sql` (CI'da forward/rollback ve non-superuser owner ile doğrulanıyor). Uygulanması kullanıcı onayı gerektirir.

### 5.4 Supabase: eksik tablolar (salt-okunur doğrulandı)

`public.user_notes` ve `public.note_reviews` production'da **yok** (`to_regclass` NULL). Notlar ve tekrar (spaced repetition) özellikleri production'da çalışamaz; ilgili migration'lar (09, 10) uygulanmamış görünüyor. Uygulanmaları onay gerektirir; uygulanmadı.

### 5.5 Platformlar

| Platform | Durum |
|---|---|
| Render | Yapılandırma dashboard'da; repoda `render.yaml` yok. Shell'de bir `RENDER_API_KEY` tanımlı; env değişkenlerinin *adlarını* okuma denemesi Claude Code izin sistemi tarafından engellendi ve tekrar denenmedi. Bu yüzden Render env'i doğrulanmadı. Gunicorn 1 worker. |
| Vercel | Bağlayıcı yetkisiz; yalnızca PR status check'i (SUCCESS) görüldü. Repoda `vercel.json` yok. |
| Supabase | Salt-okunur olarak incelendi (5.3, 2.3). |
| Gemini | 2.2. |
| CI/CD | `permissions: contents: read`, secret kullanımı yok, `pull_request_target` yok, concurrency iptali var. `paths-ignore: **.md`, bu yüzden yalnızca doküman içeren commit'ler CI'ı tetiklemez. |

---

## 6. Test Sonuçları

| Komut | Ortam | Sonuç | Geçen | Başarısız | Atlanan | Açıklama |
|---|---|---|---|---|---|---|
| `pytest backend/tests/` | Yerel, yeni pinler (Flask-Cors 6.0.5, pytest 9.0.3) | ✅ | 1216 | 0 | 0 | 22 deselected (integration/external/e2e marker'ları; `pytest.ini`). Bir önceki koşu (1213) `-W error::PytestRemovedIn10Warning` ile yapıldı. |
| `pytest backend/tests/test_rag*.py` | Yerel | ✅ | 357 | 0 | 0 | CI'daki RAG adımıyla aynı komut |
| `ruff check backend/` | Yerel | ✅ | – | 0 | – | |
| `pip-audit -r backend/requirements-test.txt` | Yerel | ✅ | – | 0 bilinen açık | – | |
| `npm run lint` / `tsc --noEmit` / `npm run build` | Yerel | ✅ | – | 0 | – | |
| `npm test` | Yerel | ✅ | 248 | 0 | 0 | |
| CI `44941994490` (başlangıç, `795ca3c`) | GitHub | ❌ | 341 | 3 | – | RAG adımı başarısız; Fast Suite, E2E ve Visual QA atlandı |
| CI `44944963348` (`d193d4f`) | GitHub | ✅ 8/8 iş | Fast 1149 | 0 | 9 | Katalog sınır testleri 19/19. 9 atlanan: `test_local_vertical_slice` (CI'da embedded Postgres yok) |
| CI `44946907198` (`7921add`) | GitHub | ✅ 8/8 iş | E2E 86 | 0 | 3 | 1 flaky (düzeltildi, `7231772`). 3 atlanan: yalnızca-telefon testi (desktop'ta) ve README ekran görüntüsü üreticisi (2 proje) |
| CI `44948889863` (`cac5fdb`) | GitHub | ✅ 9/9 iş (yeni Python audit işi dahil) | RAG 357 · Fast 1204 · E2E 87 | 0 | Fast 9 · E2E 3 | Flaky yok |
| CI `44949645948` (`75081ba`, son) | GitHub | ✅ 9/9 iş | RAG 357 · Fast 1207 · E2E 87 | 0 | Fast 9 · E2E 3 | Flaky yok |

**Mutasyon kontrolleri** (testlerin gerçekten bir şey yakaladığı doğrulandı): Tie-order testleri eski kodda tam olarak CI'daki üç senaryoda başarısız. Eski anahtar önceliği olay senaryosunu kırıyor. Paylaşılan durum (thread-local yerine) per-thread testini kırıyor. Mutlak import script testini kırıyor. Eski `app.py`'de 9 HTTP testinin 5'i başarısız (diğer 4'ü zaten doğru olan davranışı sabitliyor).

**Yerel ortam sapması:** Global Python'da Flask-Cors **4.0.0** kurulu (pin 4.0.2 idi, artık 6.0.5). `pip install -r backend/requirements-test.txt` çalıştırılmazsa `test_cors_contract.py::test_private_network_access_is_not_granted` yerelde başarısız olur. Kullanıcının global ortamına dokunulmadı; doğrulama izole venv'de yapıldı.

---

## 7. Git ve PR

| Commit | Açıklama |
|---|---|
| `d193d4f` | fix(recommender): MMR aday ve lexical fallback için deterministik eşitlik sırası |
| `1ef6eea` | fix(ai): sohbet ve embedding için tek Gemini anahtar kuralı; fallback nedenini raporlama |
| `7921add` | fix(embeddings): embedding_service'in top-level paket olarak import edilebilmesi |
| `60f01a1` | fix(api): 1 MiB gövde sınırı; werkzeug HTTP hata kodlarının korunması |
| `5fe6fde` | fix(api): `X-Request-Id` yalnızca id biçimindeyse kabul |
| `7231772` | test(e2e): görünür add-book ipucunun doğrulanması (flaky) |
| `cac5fdb` | fix(security): Flask-Cors 6.0.5, private-network reddi, `Vary: Origin`, CI pip-audit |
| `75081ba` | fix(activity): `user_activities` insert'ünde `return=minimal` (production 42501) |
| (bu rapor) | docs: mühendislik denetim raporu |

- **Değişen dosyalar:**
  - `backend/infrastructure/ml/recommender.py`
  - `backend/config.py`
  - `backend/container.py`
  - `backend/services/embedding_service.py`
  - `backend/infrastructure/llm/adapters.py`
  - `backend/application/use_cases/ai_rag.py`
  - `backend/app.py`
  - `backend/requirements.txt`
  - `backend/infrastructure/persistence/supabase_adapters.py`
  - `.github/workflows/ci_cd.yml`
  - `web/e2e/core-journeys.spec.ts`
  - testler: `test_rag_explanation_labels.py`, `test_llm_adapter_resilience.py` ve yeni `test_llm_key_and_failure_category.py`, `test_http_error_contract.py`, `test_cors_contract.py`, `test_activity_insert_returning.py`
  - bu rapor
- **PR #95:** açık, mergeable. **Merge edilmedi, deploy yapılmadı, force push yapılmadı.**
- **API sözleşmesi:** Yalnızca ekleme yapıldı: `metrics.llm_error`, 413 gövdesi ve `Vary` header'ı. Mevcut alanlar ve durum kodları korundu; tek bilinçli değişiklik, önceden yanlışlıkla 500 dönen HTTP hatalarının artık gerçek kodlarıyla dönmesi.

---

## 8. Tamamlanmayan İşler

| Ne eksik? | Neden? | Gereken erişim/onay | Nasıl tamamlanır? |
|---|---|---|---|
| **01c'nin production'a uygulanması** (5.3) | Production migration'ı kullanıcı onayı gerektirir. | Onay ve Supabase SQL Editor. | `backend/scripts/hardening/MIGRATION_*` dokümanlarına göre önce staging; ardından `01c_DRAFT_catalog_write_lockdown.sql` → `verify_01c_…sql` (0 FAIL beklenir). Rollback script'i hazır. |
| **Production sohbet 401** | Kod düzeltmesi merge ve deploy bekliyor; Render env değişkenleri görülemiyor. | Render dashboard ve merge onayı. | **Hemen (deploy gerektirmez):** Render'da `LLM_API_KEY`'i silin veya yeni anahtarla güncelleyin. Ardından PR'ı merge edin; açılış logunda çakışma uyarısı görünmemeli. |
| 120 sorguluk canlı RAG değerlendirmesi | ~285 Gemini çağrısı (2.5); onay gerekir. | Onay; tercihen production'dan ayrı bir anahtar. | `python -m backend.scripts.run_rag_quality_eval run`, ardından `report`. |
| İnsan etiketleri | 1.184 etiketin 0'ı insan tarafından doğrulanmış. | İnsan değerlendirici. | `data/rag_review_queue.csv` ve `evaluation/REVIEW_GUIDE.md`. |
| Render `DATABASE_URL` ve anahtar kontrolü | Render API okuma isteği izin sistemi tarafından engellendi. | Render dashboard veya izin. | `DATABASE_URL` tanımlıysa RLS bypass'ı bilinçli olmalı (3.3). `LLM_API_KEY`'in durumu da burada kontrol edilmeli. |
| `user_notes` / `note_reviews` tabloları | Production migration'ı onay gerektirir. | Onay ve Supabase SQL Editor. | Script 09 ve 10'u, önce staging'de olmak üzere sırayla uygulamak. |
| Vercel Preview'ün fonksiyonel doğrulaması | Bağlayıcı yetkisiz; preview backend yok. | Vercel yetkisi ve bir preview backend. | Claude.ai bağlayıcı ayarlarından Vercel yetkisi. |
| Manuel responsive ve ekran okuyucu QA | Bu oturumda yapılmadı. | – | Gerçek cihazlarda, NVDA/VoiceOver ile. |
| Gemini timeout bütçesi | Ölçmeden değiştirilmedi. | Canlı ölçüm. | Toplam süre (deadline) bazlı timeout ve retry'ı p95 verisiyle ayarlamak. |

---

## 9. Riskler

| Seviye | Risk |
|---|---|
| **Kritik** | Production `books`: anon/authenticated INSERT ve UPDATE (5.3). Katalog bütünlüğü bozulabilir ve RAG context'ine prompt injection yapılabilir. |
| **Yüksek** | Production sohbet 401 (fix deploy edilmedi; Render env düzeltmesi bekleniyor). |
| **Yüksek** | Production'da `user_notes` ve `note_reviews` tabloları yok: notlar ve tekrar özellikleri çalışmıyor. |
| **Yüksek** | Gemini generation p95 15 sn / max 24 sn, tek sync worker: yavaş istekler diğerlerini bekletir. |
| Orta | Değerlendirme etiketlerinin tamamı LLM-geçici; kalite iddiaları insan doğrulaması olmadan zayıf. |
| Orta | `DATABASE_URL` tanımlıysa kullanıcı verisinde RLS atlanır (yalnızca uygulama filtresi kalır). |
| Orta | 120 sorgunun 76'sı canlı ölçülmedi. |
| Düşük | Postgres adaptöründe `connect_timeout` yok; kopan bağlantı bir isteği düşürür. |
| Düşük | Not aramasında ILIKE joker karakterleri escape edilmiyor. |
| Düşük | Yerel Python ortamı pinlerden sapmış (Flask-Cors 4.0.0). |

---

## 10. Nihai Değerlendirme

| Alan | Puan | Gerekçe |
|---|---|---|
| AI / RAG | **6/10** | Grounding, dürüst fallback, degraded etiketleri ve offline harness güçlü; determinizm ve anahtar tutarlılığı düzeltildi. Ancak production sohbeti şu an çalışmıyor, etiketlerin 0'ı insan onaylı, 76 sorgu canlı ölçülmedi, p95 15 sn. |
| Backend | **7/10** | Kimlik doğrulama özenli, parametreli SQL, iyi test kapsamı; gövde sınırı ve HTTP kodları düzeltildi. Tek worker, metrics endpoint'i yok, doğrudan DB yolunda RLS yok. |
| Frontend | **7/10** | Lint, typecheck, 248 unit test, build ve 86 E2E geçiyor; erişilebilir resimler, dürüst AI etiketleri. Manuel görsel/responsive/ekran okuyucu QA bu oturumda yapılmadı, bu yüzden daha yüksek puan verilmedi. |
| Security | **4/10** | Kod tarafı iyi (secret sızıntısı yok, CVE'ler giderildi, CORS testli). **Production'daki katalog yazma açığı açık.** Puan, production'ın gerçek durumunu yansıtıyor. |
| Testing | **8/10** | 1.213 backend + 248 web + 86 E2E test, mutasyonla doğrulanmış regresyon testleri, CI'da migration doğrulaması. Eksikler: CI'da 9 atlanan vertical-slice testi ve canlı değerlendirmenin CI dışında kalması. |
| Production Readiness | **4/10** | Üç yüksek/kritik production sorunu (katalog yazma, sohbet 401, eksik not tabloları) kod dışı aksiyon bekliyor. İkisi de giderildikten ve PR merge edildikten sonra yeniden değerlendirilmeli. |
