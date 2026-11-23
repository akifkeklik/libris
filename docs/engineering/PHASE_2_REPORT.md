# Faz 2: Hesap Temelleri ve Veri Hakları

**Branch:** `feat/phase-2-account-basics` · **Durum:** kod tamamlandı ve test edildi. Production adımları (migration ve Supabase ayarları) sizde.

## 1. Doğrulama: başlangıçta ne vardı?

| Özellik | Durum |
|---|---|
| Şifre sıfırlama | **Yoktu.** Ne e-posta bağlantısını oturuma çeviren callback route'u ne de "şifremi unuttum" sayfası vardı. |
| Google ile giriş | **Yoktu.** |
| Hesap silme | **Yoktu.** Ayrıca production'da (read-only kontrol) `favorites` ve `user_activities` tablolarının `auth.users`'a bağlantısı **NO ACTION**. Bu yüzden favorisi ya da aktivitesi olan bir kullanıcı **Supabase panelinden bile silinemiyordu.** |
| Veri dışa aktarma | **Kısmen vardı:** yalnızca notları Markdown olarak dışa aktarıyordu. |
| Yasal sayfalar | **Yoktu.** |
| Ek bulgu | Giriş ve kayıt düğmelerinde **İngilizce sabit metinler** vardı ("Log in", "Sign up", "Creating account..."). Hepsi çevrildi. |

## 2. Yapılanlar

| Commit | Değişiklik |
|---|---|
| `2ecac21` | **Şifre sıfırlama:** `/forgot-password` sayfası. Her durumda (hesap yoksa ve hata olursa da) aynı mesaj gösteriliyor, böylece form kimin kayıtlı olduğunu öğrenmek için kullanılamıyor. `/auth/callback`: e-postadaki kodu oturuma çeviriyor; yönlendirmeye yalnızca site içi adreslere izin veriyor. `/reset-password`: yeni şifre (en az 8 karakter) ve tekrarı; süresi dolmuş bağlantıyı açıkça söylüyor. |
| `6ee8bfd` | **Google ile devam et:** giriş ve kayıt sayfalarında. Supabase'de sağlayıcı açılmadan bozuk bir buton görünmesin diye `NEXT_PUBLIC_AUTH_GOOGLE_ENABLED=true` olmadan gizli. |
| `7282ba3` | **Hesap silme (backend):** Migration 16 (idempotent). (1) `auth.users`'a bağlanan tüm foreign key'leri `ON DELETE CASCADE` yapıyor. (2) `delete_my_account()` fonksiyonu yalnızca çağıran kullanıcıyı siliyor; `books.added_by` alanını boşaltıyor (eklediği kitap katalogda kalıyor). Endpoint: `DELETE /api/account` ve `{"confirm": true}`. |
| `222b326` | **Hesap silme (arayüz):** Ayarlar → Hesap. Kullanıcı kendi e-posta adresini yazmadan silme düğmesi etkinleşmiyor. Başarılı olunca oturum kapatılıp ana sayfaya dönülüyor. Migration uygulanmadıysa "hiçbir şey silinmedi" diye dürüst bir mesaj çıkıyor. |
| `68a55c3` | **Tam veri dışa aktarma:** `GET /api/account/export?format=json|markdown`. Profil, kütüphane, favoriler, notlar (sayfalanarak, kesilmeden), not tekrarları, tekrar kartları ve tekrar geçmişi. Eksik bir kaynak (örneğin production'da olmayan tablolar) `unavailable_sections` altında belirtiliyor; geri kalan her şey yine indiriliyor. |
| `a68666f` | **Yasal sayfalar (TASLAK, 6 dil):** `/privacy` ve `/terms`. Gemini'ye ne gittiği koddan doğrulandı: önemli çıkarım metni (en fazla 1.500 karakter) ve kitap adı; yapay zekâ sohbetinde soru ve katalog bilgisi. E-posta ve hesap numarası gönderilmiyor. Analiz ya da reklam çerezi yok. |

**Brief'ten bilinçli sapma:** Hesap silme service-role anahtarıyla değil, kullanıcının kendi JWT'siyle çağrılan bir veritabanı fonksiyonuyla yapılıyor. Mevcut güvenlik sözleşmesine göre (`test_catalog_write_boundary`) çalışan backend'de service-role anahtarı bulunmamalı. Bu fonksiyon da yalnızca kendisini çağıran hesabı silebiliyor; en yetkili anahtarın sunucuya girmesine gerek kalmıyor.

## 3. Testler (hepsi çalıştırıldı)

| Komut | Sonuç |
|---|---|
| `ruff check backend/` | ✅ |
| `pytest backend/tests/` (requirements'a birebir uyan venv) | ✅ 1223 passed, 10 skipped (9'u yerelde Docker Postgres çalışmadığı için atlanan vertical-slice testleri, 1'i yalnızca eski sürüm için yazılmış test), 22 deselected |
| `npm run lint` · `npm run build` | ✅ (yeni route'lar: `/auth/callback`, `/forgot-password`, `/reset-password`, `/privacy`, `/terms`) |
| `npm test` | ✅ 259/259 |
| `npm run test:e2e` (yerelde, desktop + phone) | ✅ 87 passed, 3 skipped (bilinçli atlananlar), 0 failed |
| Migration 16, yerel PostgreSQL (pgserver) | ✅ uygulama, tekrar uygulama (idempotent), test, rollback, yeniden uygulama ve tekrar test. Silinen kullanıcının **hiçbir tabloda satırı kalmıyor**, diğer kullanıcı etkilenmiyor, kitap `added_by = NULL` olarak kalıyor. pgvector gerektiren 03–07 numaralı migration'lar yerelde atlandı; tam sıra CI'da çalışıyor (`test_16` CI'a eklendi). |
| Gerçek tarayıcı, 390×844, Türkçe | ✅ giriş ("Şifreni mi unuttun?"), şifre sıfırlama ve gizlilik sayfalarında yatay taşma yok. Şifre sıfırlama, Supabase hata verdiğinde bile aynı mesajı gösteriyor. |

**Doğrulanamadı:** Gerçek bir Supabase projesine karşı e-postayla şifre sıfırlama, Google ile giriş ve gerçek hesap silme (production'da test kullanıcısı oluşturup silmek onay gerektirir).

## 4. Production için manuel adımlar

1. **Migration 16:** Supabase SQL Editor'da `backend/scripts/16_account_deletion.sql` dosyasını çalıştırın. Ne zaman uygularsanız uygulayın, hesap silme ancak bundan sonra çalışır.
   - **Kontrol:** `SELECT conrelid::regclass, confdeltype FROM pg_constraint WHERE contype='f' AND confrelid='auth.users'::regclass;` sorgusunda tüm satırlar `c` olmalı.
   - **Geri alma:** `backend/scripts/rollbacks/16_account_deletion_rollback.sql`. Bu dosya yalnızca fonksiyonu kaldırır; CASCADE düzeltmesi bilinçli olarak kalır.
2. **Şifre sıfırlama:** Supabase → Authentication → URL Configuration → *Redirect URLs* listesine `https://<site-adresi>/auth/callback` ekleyin. Gerekirse e-posta şablonlarını Türkçeleştirin.
   - **Kontrol:** Kendi adresinizle "şifremi unuttum" deneyin. Bağlantı sizi yeni şifre sayfasına götürmeli.
3. **Google ile giriş (isteğe bağlı):**
   - Google Cloud Console'da OAuth istemcisi oluşturun. Yetkili yönlendirme adresi: `https://<proje>.supabase.co/auth/v1/callback`.
   - Supabase → Authentication → Providers → Google: Client ID ve Secret'ı girin.
   - Vercel'de `NEXT_PUBLIC_AUTH_GOOGLE_ENABLED=true` ekleyip yeniden deploy edin.
   - **Kontrol:** Giriş sayfasında "Google ile devam et" görünür ve giriş çalışır.
   - Apple ile giriş eklenmedi: ücretli Apple Developer hesabı (yıllık 99 $) gerektiriyor. Karar sizin.
4. **Yasal metinler:** `web/src/lib/legal.ts` içindeki [köşeli parantez] alanlarını doldurun: veri sorumlusu, iletişim, yurt dışı aktarım güvenceleri, yedek süresi, sorumluluk ve uygulanacak hukuk. **Gemini planınızın verileri model eğitimi için kullanıp kullanmadığını teyit edin.** Hukukçu onayından sonra TASLAK ibaresini kaldırın.

## 5. Açık riskler

- Production'da `user_notes`, `note_reviews`, `review_items` ve `review_attempts` tabloları yok (migration 09, 10 ve 13). Dışa aktarma bunları "kullanılamıyor" diye bildiriyor. Not ve tekrar özelliklerinin production'da çalışması için bu migration'lar gerekli; ayrı bir plan öneriyorum.
- Yasal metinler TASLAK; hukuki onay olmadan yayın kararı sizin.
