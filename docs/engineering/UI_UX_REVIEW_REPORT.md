# Arayüz ve Kullanıcı Deneyimi İncelemesi

**Branch:** `feat/ui-review` (Faz 2'nin üzerine) · **Durum:** bulunan sorunların hepsi düzeltildi ve doğrulandı. Ürün düzeyindeki öneriler 4. bölümde.

## 1. Nasıl incelendi?

Kodu okumakla yetinilmedi; uygulama gerçek tarayıcıda (Chromium) çalıştırılarak, bir kullanıcı gibi incelendi.

| İnceleme | Kapsam |
|---|---|
| **Giriş yapmamış ekranlar** | 16 sayfa × 4 genişlik (375, 390, 768, 1440 px) × açık ve koyu tema = 128 görünüm. Her biri için ekran görüntüsü, yatay taşma ölçümü ve axe-core erişilebilirlik taraması (zaten bağımlılıklar arasında vardı; yeni paket eklenmedi). |
| **Giriş yapmış kullanıcı yolculuğu** | Tamamen çevrimdışı bir test düzeneği: sahte Supabase (giriş ve REST) ile aynı JWT'yi doğrulayan yerel API. Kullanıcı **gerçek giriş formuyla** girip şu adımları yaptı: arama → kitap → rafa ekleme → not → kütüphane → tekrar → kişisel öneriler → yapay zekâ → ayarlar → veri indirme → hesap silme → çıkış. 390 ve 1440 px, açık ve koyu tema (4 tur × 14 adım). |

## 2. Önce ve sonra

| Ölçüt | Önce | Sonra |
|---|---|---|
| Giriş yapmamış ekranlarda ciddi/kritik axe bulgusu (açık tema, 64 görünüm) | **128** (her sayfada) | **0** (açık ve koyu) |
| Giriş yapmış yolculuk | Not ekleme adımı **başarısız**; ekran başına 2–60 bulgu | **14/14 adım**, 4 turda **0 bulgu**, 0 konsol hatası |
| Yatay taşma | 0 | 0 |
| E2E (Playwright) | 87 passed | 87 passed, 0 failed |

## 3. Bulunan ve düzeltilen sorunlar

**Kullanıcı deneyimi**
- **"Bir çıkarım ekle" düğmesi** yalnızca not bölümüne kaydırıyordu; not eklemek için ikinci bir tıklama gerekiyordu. Artık formu "önemli çıkarım" türüyle açıyor ve metin alanına odaklanıyor.
- **Giriş yapmış kullanıcının ana sayfası:** "AI'dan öneri al" düğmesi aslında yapay zekâyı değil kişisel öneri sayfasını açıyordu ve gerçek yapay zekâ düğmesiyle neredeyse aynı görünüyordu. Ürünün çekirdek döngüsüne (tekrar) giden bir düğme de yoktu. Artık ilk düğme **"Bugünün sorularını çöz"**, ardından dürüst etiketli **"Sana özel öneriler"** ve "Yapay zekâya sor" geliyor.
- **Koyu temada gri butonlar:** Tailwind'in temel sıfırlama katmanı (preflight) yüklenmediği için arka planı belirtilmemiş butonlar Chrome'un varsayılan grisiyle (#6b6b6b) çiziliyordu (tekrar sekmelerinde kontrast 2,1:1). Sıfır özgüllükte bir `:where(button)` sıfırlamasıyla tamamı düzeldi.
- **Tailwind'in `dark:` sınıfları** uygulamanın temasını değil işletim sisteminin ayarını izliyordu (açık OS + koyu Libris = yanlış renkler). Artık `data-theme`'i izliyor.
- **Sabit İngilizce metinler:**
  - "Showing N books of T", "Page X of Y", "Load More Books"
  - kitap kartlarındaki "by"
  - giriş ve kayıt düğmeleri (Faz 2'de)

  Hepsi 6 dile çevrildi.

**Erişilebilirlik (WCAG 2.1 AA)**
- **Görünen ad ile erişilebilir adın uyuşmaması (2.5.3):** arama, dil, kitap kartları, durum ve favori düğmeleri ile kişisel öneri kartları. Sesli komutla "TR" ya da "Okunuyor" diyen bir kullanıcı bu düğmelere basamıyordu.
- **Kontrast (1.4.3):** ton ve kart yüzeylerindeki metinler 2,2–4,4:1 aralığındaydı. İki türetilmiş token eklendi:
  - `--primary-strong`: %80 ana renk + metin rengi
  - `--text-muted-strong`: %70 soluk metin + metin rengi

  Bunlar **20 tema/mod bloğunun tamamında ≥ 4,6:1** sağlıyor ve `themes.test.ts` artık her yüzeyde %15'lik tonu kontrol ediyor. Opaklıkla soluklaştırılmış sayaçlar, metin rengi olarak kullanılan vurgu rengi ve koyu tema renkleriyle çizilmiş not türü rozetleri bu sayede düzeltildi.
- **Yalnızca renkle ayırt edilen bağlantılar (1.4.1):** yasal sayfa bağlantılarına alt çizgi eklendi.
- **Anlamsal HTML:** 7 sayfada iç içe iki `<main>` vardı (layout + sayfa). İçtekiler kaldırıldı.
- **Diğer:** çıkış düğmesinin adı yoktu; durum düğmeleri seçili olup olmadığını bildirmiyordu (`aria-pressed` eklendi); devre dışı sayfalama düğmesine klavyeyle ulaşılabiliyordu; not metin alanının etiketi yoktu.

## 4. Kullanıcı gözüyle kalan ürün eksikleri (kod dışı veya karar gerektiren)

| Eksik | Etki | Öneri |
|---|---|---|
| Production'da `user_notes`, `note_reviews`, `review_items` ve `review_attempts` tabloları yok | **Ürünün çekirdek vaadi (not → soru → tekrar) production'da çalışmıyor.** | 09, 10 ve 13 numaralı migration'lar; onayınızla. En yüksek öncelik budur. |
| Okuma hedefi "bu cihazda kayıtlı" | Başka bir cihazda hedef kayboluyor. | Profil tablosunda saklanması (küçük bir migration) |
| Kütüphanede elle basılan "Yenile" düğmesi | Verinin güncel olmadığı izlenimini veriyor. | Değişiklikten sonra otomatik yenileme |
| Hatırlatma (e-posta ve push) yok | Kullanıcı soruları hatırlamadıkça geri dönmüyor. | Faz 3 |

## 5. Testler (çalıştırıldı)

| Kontrol | Sonuç |
|---|---|
| `eslint src` · `tsc --noEmit` · `npm run build` | ✅ |
| `npm test` | ✅ 269/269 (yeni tema AA testi dahil) |
| `npm run test:e2e` | ✅ 87 passed, 3 skipped (bilinçli), 0 failed |
| Giriş yapmamış axe taraması | ✅ 128 görünüm, 0 ciddi/kritik bulgu |
| Giriş yapmış yolculuk | ✅ 4 tur × 14 adım, 0 bulgu, 0 konsol hatası |

**Doğrulanamadı:** Gerçek ekran okuyucu (NVDA, VoiceOver) ve fiziksel cihaz testi. axe otomatik araçtır; erişilebilirlik sorunlarının bir kısmını yakalar, hepsini değil.
