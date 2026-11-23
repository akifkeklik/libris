# Ön yüz QA raporu

Tarih: 2026-11-24. **Yöntem:** gerçek tarayıcı (Chromium) + yerel sahte Supabase + yerel backend; ekran görüntüleri gözle incelendi. Canlı sitede giriş yapılmış test, gerçek telefon, Safari ve Firefox testi **yapılmadı**.

| Akış | Ortam | Sonuç |
|---|---|---|
| Genel e2e (katalog, kitap, sohbet, 6 dil, temalar, telefon) | masaüstü + telefon | 87 geçti, 3 atlandı |
| Erişilebilirlik (axe, ciddi/kritik; Faz 3 öncesi ekranlar) | 4 yapılandırma | 0 bulgu. Sonradan eklenen `/import`, kart menüsü ve açılır menüde axe **çalıştırılmadı** |
| Kayıtlı e-postayla kayıt → e-posta dolu giriş | 1280 koyu, 390 açık | geçti |
| Beni hatırla kapalı → oturum çerezi tarayıcı kapanınca biter | aynı | geçti (çerez süresi ölçüldü) |
| Açılır menü: fare, klavye, Esc, dışarı tıklama | aynı | geçti |
| Menü çubuğu: 6 dil × 6 genişlik × giriş var/yok | 72 durum | taşma ve satır kırma 0 |
| İçe aktarma: yükle, tekrar yükle, kitap seç, onayla | 1280 koyu | geçti. Telefonda yalnızca boş kuyruk görüntüsü incelendi |
| Kart: düzenle, yeni soru (model yokken), bildir, yenile | 1280 koyu, 390 açık | 11/11 ikisinde de |
| Ayarlar: hatırlama hedefi, Anki indirme | aynı | geçti |
| Canlı: ana sayfa, `/import`, ikon | HTTP | 200 |

## QA sırasında bulunup düzeltilenler

Sunucu tarafında `document is not defined`; menü çubuğunun taşması; bildirilen kartın geri gelmesi; telefonda kesilen sekmeler; kartta kitap adının görünmemesi; kesik açılır menü metni; iki çevrilmemiş İngilizce metin.

## Elle denenmesi gerekenler (sizde)

- [ ] iPhone: ana ekrana ekle → bildirim izni → bildirim
- [ ] Android: Libris'i yükle → başka uygulamadan dosya/metin paylaş
- [ ] Gerçek e-posta: gelen kutusu, abonelikten çıkma düğmesi
- [ ] `.apkg` dosyasını Anki'de aç, ikinci kez içe aktar (kopya oluşmamalı)
- [ ] Safari ve Firefox'ta giriş, açılır menü, içe aktarma
- [ ] Şifre sıfırlama e-postası ve hesap silme (test hesabıyla)
