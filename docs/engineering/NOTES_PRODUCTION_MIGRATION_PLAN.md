# Notlar ve Tekrar Tabloları: Production Migration Planı

**Durum: PENDING APPROVAL.** Migration'lar production'da **çalıştırılmadı**. Bu doküman uygulama planıdır.

## 1. Sorun

Libris'in ürün vaadi şu döngüye dayanıyor: "Okurken önemli bir çıkarımı kaydet → Libris onu soruya çevirsin → tam unutmadan önce tekrar sorsun." Bu döngünün tabloları production'da **yok**. 2026-11-22'de read-only olarak doğrulandı:

| Tablo | Migration | Production'da |
|---|---|---|
| `public.user_notes` | 09 | **yok** |
| `public.note_reviews` | 10 | **yok** |
| `public.review_items` | 13 | **yok** |
| `public.review_attempts` | 13 | **yok** |

**Sonuç:** Production'da not kaydetme, tekrar kartları ve tekrar geçmişi çalışamaz. Veri dışa aktarma bu bölümleri dürüstçe "unavailable" olarak bildiriyor.

## 2. Ön kontrol (read-only, production, 2026-11-22)

| Kontrol | Sonuç |
|---|---|
| `auth.users` var mı? | ✅ var (22 kullanıcı) |
| Aynı adla bir tablo, index veya politika var mı? | ✅ yok; çakışma yok |
| `authenticated` rolünün `public` şemasında USAGE ve `auth.uid()` üzerinde EXECUTE yetkisi | ✅ var |
| `learning_paths` (11) | yok. 13 buna bağlı değil; yalnızca `source_type` değerlerinden biri bu adı taşıyor. |

## 3. Migration'lar ve sırası

1. `backend/scripts/09_learning_notes.sql`: `user_notes`, 3 index, RLS ve kendi satırı politikaları (select, insert, update, delete)
2. `backend/scripts/10_learning_notes_idempotency_and_review.sql`: `client_id` tekil index'i (çift kaydı önler), `note_reviews` tablosu, RLS
3. `backend/scripts/13_learning_outcomes.sql`: `review_items` ve `review_attempts` tabloları, index'ler, RLS
4. (Faz 2 PR'ı merge edildiyse) `backend/scripts/16_account_deletion.sql`: hesap silme. Yeni tablolar zaten `ON DELETE CASCADE` ile tanımlı.

**Özellikler:**
- Hepsi idempotent (`CREATE TABLE IF NOT EXISTS`, `DROP POLICY IF EXISTS`): tekrar çalıştırmak bir şeyi bozmaz.
- Yalnızca `auth.users`'a ve birbirlerine bağlılar.
- Mevcut hiçbir tabloyu değiştirmiyorlar; **veri silme ya da taşıma yok.**

## 4. Kanıt (çalıştırıldı)

| Test | Sonuç |
|---|---|
| CI'daki tam migration sırası (pgvector'lü PostgreSQL 16) | ✅ her PR'da çalışıyor |
| Yerel PostgreSQL'de 00–16 sırası (pgvector gerektiren 03–07 hariç) | ✅ |
| **RLS izolasyon testi** (`backend/tests/sql/test_09_10_13_rls_isolation.sql`), gerçek `authenticated` rolüyle | ✅ **ALL CHECKS PASSED** |
| Aynı test, bilerek gevşetilmiş bir politikayla (mutasyon kontrolü) | ✅ testi **kırdı**: "B sees 1 of A's notes". Test sızıntıyı gerçekten yakalıyor. |

İzolasyon testinin kontrol ettikleri: B okuru, A'nın 4 tablodaki hiçbir satırını **göremiyor**; A'nın notunu **değiştiremiyor**, tekrar kartını **silemiyor**; A adına satır **yazamıyor** (42501); ve A'nın verisi bozulmuyor. Test CI'a eklendi.

## 5. Uygulama adımları (onayınızla)

1. Supabase → SQL Editor'da sırasıyla 09, 10 ve 13'ü çalıştırın. Her biri tek başına güvenli; hata alırsanız durun ve bana iletin.
2. **Doğrulama (read-only):**
   ```sql
   SELECT c.relname, c.relrowsecurity,
          (SELECT count(*) FROM pg_policies p WHERE p.schemaname='public' AND p.tablename=c.relname) AS policies
   FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='public' AND c.relname IN ('user_notes','note_reviews','review_items','review_attempts');
   ```
   **Beklenen:** 4 satır; hepsinde `relrowsecurity = true`. Politika sayıları: `user_notes` 4, `note_reviews` 4, `review_items` 4, `review_attempts` 3.
3. **Uygulamada:**
   - Bir kitapta "Bir çıkarım ekle" → not kaydedilir ve "soru olarak eklendi" kartı görünür.
   - **Tekrar** sekmesinde soru listelenir.
   - Ayarlar → Verilerimi indir dosyasında `unavailable_sections` artık bu bölümleri içermez.

## 6. Geri alma

- Tablolar yeni ve boş başladığı için geri alma, tabloları silmek anlamına gelir: `DROP TABLE public.review_attempts, public.review_items, public.note_reviews, public.user_notes;`
- **Dikkat:** Kullanıcılar not yazmaya başladıktan sonra bu işlem **o verileri siler**. Önce dışa aktarmadan geri almayın.
- Kod tarafında değişiklik gerekmez: uygulama bu tablolar olmadan da çalışıyor; yalnızca not ve tekrar özellikleri devre dışı kalıyor.

## 7. Risk

**Düşük.** Yeni tablolar oluşturuluyor; mevcut veriye dokunulmuyor. Kısa süreli kilit yalnızca `auth.users`'a eklenen foreign key'ler sırasında alınıyor (milisaniyeler).
