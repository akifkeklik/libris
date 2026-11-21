# Faz 0: Production Runbook

Bu runbook'taki adımları **siz** uygulayacaksınız. Kodun hazırlandığı branch'ler `ai-subsystem-audit` (PR #95) ve `feat/phase-0-trust-reliability`. Burada hiçbir adım otomatik çalıştırılmadı. Her adımın sonunda "doğru çalıştığını nasıl anlarım" kontrolü var. Secret değerlerini hiçbir yere yapıştırmayın; yalnızca değişken adları yazılmıştır.

## Doğrulama özeti: bulgular gerçekten var mıydı?

| Bulgu | Doğrulama (2026-11-22, production'da read-only) | Sonuç |
|---|---|---|
| Chat 401, eski `LLM_API_KEY` | Sohbet `LLM_API_KEY`'i öncelikli kullanıyordu, embedding ise `GEMINI_API_KEY`'i (kod okuma ve mutasyon testi). | **Doğru.** Kod düzeltmesi `1ef6eea`'da; açılışta anahtar eksikse bir kez loglanıyor (`cd4c6c5`). Render env düzeltmesi sizde (adım 1). |
| Kataloğa anonim yazma | `verify_01c`: 33 FAIL; `python_ekleme_izni` / `python_guncelleme_izni` politikaları mevcut. | **Doğru.** Migration hazır ve CI'da testli. Plan: `PRODUCTION_CATALOG_SECURITY_PLAN.md` (adım 3). |
| Semantic arama devre dışı / RPC'ler eksik | `match_query_embeddings` **var**: canlı değerlendirmede 120/120 başarılı çağrı. `match_book_embeddings` **yok**. HNSW index var. | **Kısmen doğru.** Ask-AI semantic aramada çalışıyor. Seed tabanlı kişisel öneriler ve "benzer kitaplar" TF-IDF'e düşüyor; bu `retrieval_mode = tfidf_fallback` olarak görünür biçimde etiketleniyor. Migration zaten mevcut ve CI'da testli (adım 4). |
| Embedding backfill yapılmamış | `backfill_embeddings.py --check`: 6.446 kitabın 6.446'sı güncel, yeniden embed edilecek 0. | **Yanlış.** Backfill gerekmiyor. Script zaten idempotent: içerik hash'i ve profil karşılaştırıyor, güncel olanları atlıyor ve yalnızca eksikleri işliyor. |
| supabase-py 2.3 `sb_publishable_` kabul etmiyor | İzole venv'lerde sentetik anahtarla denendi: 2.10.0 ve 2.15.0 reddediyor, 2.18.0 kabul ediyor. Yerelde çalışıyormuş gibi görünmesinin nedeni, shell'deki eski JWT anahtarının `.env`'i ezmesi. | **Doğru.** 2.18.1'e yükseltildi (`d0c189b`). Gerçek publishable anahtarla production'da read-only smoke testi geçti (SELECT, RPC, auth). |

---

## Adım 0: Ön koşul (bir kez)

Production'ın bugünkü durumunu kaydedin. Supabase Dashboard → SQL Editor'da `backend/scripts/hardening/verify_01c_catalog_write_lockdown.sql` dosyasının içeriğini çalıştırın. Bu sorgu read-only'dir (`BEGIN READ ONLY … ROLLBACK`).
**Beklenen:** `OVERALL … 33 FAIL / 1 WARN / 58 checks`. Farklı bir sonuç görürseniz durun ve bana bildirin.

## Adım 1: Render ortam değişkenleri (chat 401)

1. Render Dashboard → `libris-api` → **Environment** bölümüne gidin.
2. `GEMINI_API_KEY`'in tanımlı olduğunu kontrol edin. Embedding'in çalıştığı anahtar budur.
3. `LLM_API_KEY` değişkenini **silin**. (Yeni kod bu değişkene yalnızca `GEMINI_API_KEY` yoksa bakıyor. Eski kod hâlâ deploy'daysa, sohbeti hemen düzelten adım da budur.)
4. `LLM_PROVIDER` ya tanımsız olmalı ya da `gemini` olmalı.
5. **Save, rebuild and deploy.**

**Doğru çalıştığını nasıl anlarım:**
- Deploy loglarında `No API key for LLM_PROVIDER` **ve** `GEMINI_API_KEY and LLM_API_KEY are both set and differ` satırları görünmemeli. (İkinci satır yalnızca PR #95 deploy edildikten sonra loglanır.)
- Uygulamada Ask AI'ya "Recommend a book about the Ottoman Empire" yazın. Cevabın altındaki kaynak etiketi **"Gemini"** olmalı, "Fallback" değil.
- Teknik kontrol: `POST /api/ai/chat` cevabında `metrics.source == "rag_llm"` olmalı ve `metrics.llm_error` alanı bulunmamalı. `llm_error == "auth"` görürseniz anahtar hâlâ geçersizdir.

## Adım 2: Kodun deploy'u (merge, sizin onayınızla)

Sıra: önce PR #95 (`ai-subsystem-audit`), sonra Faz 0 PR'ı (`feat/phase-0-trust-reliability`). `main`'e merge edilen her commit Render ve Vercel production deploy'unu başlatır.

**Doğru çalıştığını nasıl anlarım:**
- `GET https://<render-url>/api/health` → 200.
- `GET /api/health/ready` → 200 `{"status":"ready"}`.
- Render loglarında `SupabaseConfigError` görünmemeli.
- 1 MiB'tan büyük bir istek 413 dönmeli (isteğe bağlı kontrol).

**Rollback:** Render → Deploys → önceki deploy → **Rollback**. Kod geri alınır; veritabanında bir değişiklik olmadığı için başka bir işlem gerekmez.

## Adım 3: Katalog yazma kilidi (01c)

Tam plan, risk analizi ve rollback: `docs/engineering/PRODUCTION_CATALOG_SECURITY_PLAN.md`.

1. SQL Editor'da `backend/scripts/hardening/01c_DRAFT_catalog_write_lockdown.sql` dosyasının tamamını çalıştırın.
2. `NOTICE: 01c OK: anon/authenticated/PUBLIC hold only SELECT …` mesajını görmelisiniz. Hata alırsanız transaction geri alınmıştır; hiçbir şey değişmemiştir.

**Doğru çalıştığını nasıl anlarım:**
- `verify_01c_catalog_write_lockdown.sql` → `OVERALL | no FAIL | 0 FAIL / 0 WARN / 58 checks | PASS`.
- Uygulamada katalog ve kitap sayfaları açılıyor, Ask AI'da semantic arama çalışıyor.
- Giriş yapmış bir kullanıcıyla "Add a book" çalışıyor (RPC ile; etkilenmez).

**Rollback:** `01c_DRAFT_catalog_write_lockdown_rollback.sql`. Bu dosya yetkileri geri verir ama permissive politikaları **geri getirmez**, yani güvenli tarafta kalır.

## Adım 4: Eksik vector RPC (`match_book_embeddings`)

1. SQL Editor'da `backend/scripts/hardening/04_DRAFT_harden_vector_rpcs.sql` dosyasını çalıştırın. Dosya:
   - önce ön koşulları kontrol eder (`vector` extension ve `book_embeddings` tablosu);
   - `match_query_embeddings`'e sabit `search_path` ve `match_count ≤ 100` sınırı ekler (SECURITY INVOKER olarak kalır);
   - eksik olan `match_book_embeddings`'i oluşturur;
   - EXECUTE iznini yalnızca `anon`, `authenticated` ve `service_role` rollerine verir.
2. `NOTICE: Doğrulama başarılı: match_query_embeddings ve match_book_embeddings aktif.` mesajını görmelisiniz.

**Doğru çalıştığını nasıl anlarım:**
- Read-only kontrol:
  ```sql
  SELECT proname, prosecdef FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
  WHERE n.nspname = 'public' AND proname LIKE 'match_%' ORDER BY 1;
  ```
  İki satır dönmeli ve ikisinde de `prosecdef = false` olmalı.
- Adım 3'ten sonra `verify_01c` hâlâ 0 FAIL vermeli. (`match_query_embeddings` SECURITY INVOKER kontrolü bunu kapsıyor.)
- Uygulamada: kütüphanesinde kitap olan bir kullanıcının kişisel önerilerinde (`/api/recommend/personalized`) `diagnostics.retrieval_mode` artık `tfidf_fallback` değil, `hybrid_semantic` olmalı.

**Rollback:** `04_DRAFT_harden_vector_rpcs_rollback.sql`. `match_book_embeddings` kaldırılır ve `match_query_embeddings` önceki tanımına döner. Uygulama yine TF-IDF fallback'ine, etiketli olarak düşer.

## Adım 5 (isteğe bağlı): Yeni Supabase anahtarına geçiş

Bu adımı yalnızca Adım 2 tamamlandıktan sonra yapın; eski kod (supabase-py 2.3) yeni anahtarı **reddeder**. Eski JWT formatındaki anon anahtar çalışmaya devam ediyor, bu yüzden geçiş acil değil.

1. Supabase → Settings → API Keys → **Publishable key** değerini kopyalayın.
2. Render'da `SUPABASE_ANON_KEY`, Vercel'de `NEXT_PUBLIC_SUPABASE_ANON_KEY` (web tarafında kullanılan ad) değerini güncelleyin ve yeniden deploy edin.

**Doğru çalıştığını nasıl anlarım:** `/api/health/ready` 200 döner, Render loglarında `SupabaseConfigError` görünmez, giriş yapılabilir ve katalog yüklenir.
**Doğrulanmadı:** Yeni anahtarı yalnızca backend'in Python istemcisiyle test ettim. Web tarafındaki `@supabase/supabase-js` sürümünün bu formatı kabul ettiğini denemedim. Vercel'i değiştirmeden önce bir preview deploy'unda giriş yapmayı deneyin.
**Rollback:** Eski anahtarı geri yazın.

## Adım 6: Backfill (gerekmiyor; yalnızca kontrol)

```bash
python backend/scripts/backfill_embeddings.py --check
```
Bu komut veritabanına yazmaz ve Gemini çağrısı yapmaz.
**Beklenen:** `Books: 6446, up to date: 6446, would embed: 0`. Yeni kitap eklendiğinde aynı script `--check` bayrağı olmadan çalıştırılır: yalnızca eksik veya bayat olanları işler (idempotent ve kaldığı yerden devam eder). Her kitap için en fazla 3 deneme yapar ve kota hatalarında (429) bekler (`generate_embedding(max_retries=3, wait_on_quota=True)`). Üst üste 3 kitap başarısız olursa çıkış koduyla durur.

---

## Faz 0 kapsamı dışında kalan, production'da bekleyen işler

- `user_notes` ve `note_reviews` tabloları production'da **yok** (migration 09 ve 10). `review_items` ve `review_attempts` de **yok** (migration 13). Notlar ve tekrar özellikleri bu yüzden production'da çalışamaz. Bunlar ürün vaadinin merkezinde, ama ayrı bir migration planı gerektiriyor; bir sonraki iş olarak öneriyorum.
- Render'da `DATABASE_URL` tanımlı mı, doğrulanamadı (Render API okuması izin sistemi tarafından engellendi). Tanımlıysa kullanıcı verisi RLS'yi atlayan doğrudan bağlantıyla okunur. Lütfen Environment listesinde kontrol edin: **tanımlı olmamalı.**
