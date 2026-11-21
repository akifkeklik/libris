# Production Katalog Güvenlik Planı (01c)

**Durum: PENDING APPROVAL.** Bu doküman bir plandır. Migration production'da **çalıştırılmadı**.
**Hazırlanma:** 2026-11-22 · **Branch:** `ai-subsystem-audit` · **Dosyalar:** `backend/scripts/hardening/01c_DRAFT_catalog_write_lockdown*.sql`

## 1. Mevcut risk

Bu bölümdeki bilgiler production'da 2026-11-22'de read-only oturumla doğrulandı (`verify_01c_catalog_write_lockdown.sql` sorgusu; sonuç: **33 FAIL / 1 WARN / 58 kontrol**).

- **`public.books`:** `anon` ve `authenticated` rollerinde INSERT, UPDATE, DELETE, REFERENCES ve TRIGGER yetkileri (tablo ve kolon düzeyinde) var. Ayrıca iki permissive yazma politikası var:

  | Politika | Komut | Rol | Koşul |
  |---|---|---|---|
  | `python_ekleme_izni` | INSERT | `public` | `WITH CHECK true` |
  | `python_guncelleme_izni` | UPDATE | `public` | `USING true` |

  **Sonuç:** Web bundle'da açıkça bulunan anon anahtarıyla, PostgREST üzerinden **herkes kitap ekleyebilir ve her kitabı değiştirebilir.** DELETE politikası olmadığı için silme RLS tarafından engelleniyor. TRUNCATE yetkisi zaten kaldırılmış (01_PROD ile).
- **`public.book_embeddings`:** Aynı yazma yetkileri mevcut, ama yalnızca bir SELECT politikası var; bu yüzden yazmalar RLS tarafından engelleniyor. Bu güvence tek bir politika eksikliğine dayanıyor: biri yanlışlıkla bir yazma politikası eklerse açık hemen oluşur.
- **AI etkisi:** Kitap açıklamaları LLM context'ine giriyor. Değiştirilebilen bir açıklama, RAG cevaplarına prompt injection yolu açar.
- **Kanıt sınırı:** Açık, yetki ve politika semantiğinden çıkarıldı; production'a yazma denemesi **yapılmadı**. Aynı durum CI'daki test veritabanında anon ile INSERT/UPDATE yapılarak kanıtlanıyor (`test_01c_…_runtime.sql`, adım 1).
- **Kurcalama izi bulunmadı:** 2026-10-03'ten sonra eklenmiş kitap yok. 6.446 kitabın güncel metni, embedding'in üretildiği hash ile eşleşiyor.

## 2. Etkilenen tablolar ve yetki sınırları

| Nesne | Şimdi (anon/authenticated) | 01c sonrası |
|---|---|---|
| `public.books` | SELECT, INSERT, UPDATE, DELETE, REFERENCES, TRIGGER; 2 permissive yazma politikası | Yalnızca **SELECT**; yazma politikası yok |
| `public.book_embeddings` | SELECT, INSERT, UPDATE, DELETE, REFERENCES, TRIGGER | Yalnızca **SELECT** |
| `PUBLIC` pseudo-rolü | Yazma yetkisi yok (PASS) | Değişmez |
| RLS / FORCE RLS / tablo sahipliği | RLS açık, FORCE kapalı, sahip `postgres` | **Değişmez** |
| `add_catalog_book` RPC | SECURITY DEFINER, sahibi books'un sahibi; `authenticated` çalıştırabilir | **Değişmez** |
| `match_query_embeddings` | SECURITY INVOKER; anon ve authenticated çalıştırabilir | **Değişmez** (SELECT yetkisi korunduğu için çalışmaya devam eder) |
| `service_role`, diğer tablolar, sequence'ler | – | **Dokunulmaz** |

## 3. Politika listesi: önce ve sonra

| Tablo | Politika | Önce | Sonra |
|---|---|---|---|
| books | `Herkes kitaplari okuyabilir` (SELECT, `true`) | var | **var** |
| books | `python_ekleme_izni` (INSERT, `true`) | var | **silinir** |
| books | `python_guncelleme_izni` (UPDATE, `true`) | var | **silinir** |
| book_embeddings | `Embeddings are readable by everyone` (SELECT, `true`) | var | **var** |

## 4. Yetkili yazma akışı (01c sonrası; hepsi doğrulandı)

| Akış | Mekanizma | 01c etkisi | Kanıt |
|---|---|---|---|
| Okuyucu kitap katkısı (`POST /api/books`) | `add_catalog_book` RPC, SECURITY DEFINER, tablo sahibi olarak INSERT yapar; günlük kullanıcı limiti var | Yok | Production'da PASS: RPC var, SECURITY DEFINER, sahibi books'a yazabiliyor, `authenticated` EXECUTE edebiliyor. CI adım 5: authenticated katkı yapabiliyor, anon yapamıyor. |
| Toplu katalog yükleme (`upload_books_to_supabase.py`) | `SUPABASE_SERVICE_ROLE_KEY` zorunlu (fail-closed) | Yok (service_role'e dokunulmaz) | Kod: `upload_books_to_supabase.py:26-37` |
| Embedding backfill (`backfill_embeddings.py`) | Doğrudan PostgreSQL, `postgres` rolü | Yok | Preflight: "RLS does not restrict this role" |
| Runtime embedding upsert (`supabase_adapters.py:464`, best-effort) | Anon client ile `book_embeddings` upsert | **Değişiklik yok**: bugün de RLS tarafından engelleniyor (yazma politikası yok) | Production politika listesi |
| Kitap okuma, arama, vector RPC | SELECT | Yok (SELECT açıkça tekrar GRANT ediliyor) | CI adım 4 |

**Kullanıcı işlemlerine etkisi:** Kullanıcı tablolarına (notlar, kütüphane, aktiviteler) dokunulmuyor. Bugün çalışan hiçbir istemci akışı books veya book_embeddings'e doğrudan yazmıyor (`test_catalog_write_boundary.py` bunu kod düzeyinde zorunlu kılıyor; CI'da 19/19).

## 5. Migration SQL

Uygulanacak dosya: `backend/scripts/hardening/01c_DRAFT_catalog_write_lockdown.sql` (123 satır). Özeti:

```sql
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

DROP POLICY IF EXISTS "python_ekleme_izni" ON public.books;
DROP POLICY IF EXISTS "python_guncelleme_izni" ON public.books;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON TABLE public.books, public.book_embeddings
    FROM anon, authenticated, PUBLIC;

GRANT SELECT ON TABLE public.books, public.book_embeddings TO anon, authenticated;

-- Transaction içi doğrulama (fail-closed): kalan bir yazma yetkisi, kalan bir
-- politika veya kaybedilen SELECT RAISE EXCEPTION'a yol açar ve hiçbir şey commit edilmez.
DO $$ ... $$;
COMMIT;
```

- **Idempotent:** `DROP POLICY IF EXISTS`; REVOKE ve GRANT tekrarlanabilir. CI adım 2'de dosya iki kez uygulanıyor ve ikinci koşudan sonra ACL, politika, sahiplik ve RLS anlık görüntüsünün ilkiyle aynı olduğu karşılaştırılıyor.
- **Atomik:** Tek transaction; doğrulama başarısız olursa her şey geri alınır.

## 6. Pre-migration kontrolleri (read-only)

1. `verify_01c_catalog_write_lockdown.sql` (Supabase SQL Editor'da güvenli; `BEGIN READ ONLY … ROLLBACK`). **Beklenen:** bugünkü durum, yani 33 FAIL ve 1 WARN; 2026-11-22'deki sonuç bu planın eki niteliğinde. Ayrıca 01c'nin varsayımlarına ait 24 PASS satırının hepsi bugün PASS olmalı: SELECT yetkileri, RLS açık, FORCE kapalı, `add_catalog_book` SECURITY DEFINER ve sahip uyumu, `match_query_embeddings` SECURITY INVOKER, EXECUTE yetkileri. Herhangi biri FAIL ise **durun**; plan o durum için yazılmadı.
2. Politika listesinin bölüm 3'teki "Önce" sütunuyla aynı olduğunu kontrol edin:
   ```sql
   SELECT tablename, policyname, cmd, roles, qual, with_check
   FROM pg_policies WHERE schemaname='public' AND tablename IN ('books','book_embeddings')
   ORDER BY 1,2;
   ```
3. İsteğe bağlı yedek (yalnızca ACL ve politikalar):
   ```sql
   SELECT relname, relacl FROM pg_class WHERE oid IN ('public.books'::regclass,'public.book_embeddings'::regclass);
   ```

## 7. Post-migration doğrulama

1. `verify_01c_catalog_write_lockdown.sql` → **OVERALL `0 FAIL / 0 WARN / 58 checks` PASS** (CI'da iki farklı sahiplik kurulumunda bu sonuç alındı).
2. Uygulama smoke testi:
   - `GET /api/books?page=1` 200 döner.
   - Bir Ask-AI sorgusunda `retrieval_mode` semantic olur (vector RPC SELECT ile çalışıyor).
   - Giriş yapmış bir kullanıcıyla "Add a book" akışı çalışır (RPC).
3. Anon ile negatif test, **yalnızca onayla ve yalnızca var olmayan bir ISBN ile:** `POST {SUPABASE_URL}/rest/v1/books` beklenen sonuç 401 veya 403 (42501). Satır oluşmamalıdır.

## 8. Rollback SQL

Dosya: `01c_DRAFT_catalog_write_lockdown_rollback.sql`. Tablo yetkilerini (INSERT, UPDATE, DELETE, REFERENCES, TRIGGER) geri verir, ama **iki permissive politikayı ve TRUNCATE'i geri getirmez**. RLS açık ve yalnızca SELECT politikaları varken geri verilen yetkiler istemci yazmasına yine izin vermez. Rollback yani "güvenli tarafta" kalır. Açığı tekrar açmanın tek yolu politikaları elle yeniden oluşturmaktır, ve bu bilinçli olarak dışarıda bırakıldı.

> `01b_DRAFT_…_rollback.sql`'i 01c'yi geri almak için kullanmayın: o dosya iki permissive politikayı yeniden oluşturur.

## 9. Kesinti ve riskler

| Risk | Olasılık | Etki | Önlem |
|---|---|---|---|
| `DROP POLICY` ve `REVOKE`, books/book_embeddings üzerinde kısa süreli ACCESS EXCLUSIVE kilit alır | Kesin, çok kısa (ms) | Bu sırada gelen okumalar bekler | `lock_timeout = 5s`: kilit alınamazsa migration hata verir ve hiçbir şey değişmez. Backend kataloğu açılışta belleğe aldığı için yalnızca vector RPC'ler etkilenir. Düşük trafikli bir saatte uygulayın. |
| Bilinmeyen bir istemci anon anahtarla books'a yazıyordur | Düşük (koddaki tüm yollar incelendi) | O istemcinin yazmaları 42501 ile reddedilir | Bu zaten istenen sonuç. Yazma gerçekten gerekiyorsa service_role veya RPC kullanmalı. |
| Production'ın CI'dan farklı bir durumda olması | Düşük | Transaction içi doğrulama başarısız olur | Fail-closed: hiçbir şey commit edilmez. |

**Beklenen kesinti:** Yok (yalnızca milisaniyeler süren bir kilit).

## 10. Uygulama adımları (onay sonrası, kullanıcı tarafından veya kullanıcının açık talimatıyla)

1. Bölüm 6'daki kontroller.
2. Supabase SQL Editor'da `01c_DRAFT_catalog_write_lockdown.sql` dosyasını çalıştırın. `NOTICE: 01c OK …` görülmeli.
3. Bölüm 7'deki kontroller.
4. Sonucu bu dokümana ekleyin ve dosya adındaki `DRAFT`'ı kaldırmak için ayrı bir commit atın.
