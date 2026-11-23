# Gemini canlıya hazırlık

Tarih: 2026-11-24. Ölçümler `AI_LIVE_EVALUATION_REPORT.md`'den (2026-11-22, **yerel backend**, gerçek Gemini). Canlı uçta yük testi yapılmadı.

## Durum

| Konu | Durum |
|---|---|
| Model | `gemini-3.5-flash-lite` (`GEMINI_MODEL` ile değişir), embedding `gemini-embedding-2` |
| Anahtar | `GEMINI_API_KEY` önceliklidir; eski `LLM_API_KEY` yalnızca o yoksa kullanılır. Çelişki loga yazılır. |
| Canlı sohbet | 22 Kasım'da canlıda test edildi, `rag_llm` döndü |
| Katalog embedding'i | 6.446 / 6.446 güncel (22 Kasım, salt okunur kontrol) |
| Zaman aşımı | 15 sn |
| Yeniden deneme | 429 ve 503'te bir kez, kısa bekleme |
| Yedek davranış | Model yoksa etiketli katalog cevabı; Gemini diye gösterilmez |
| Değerlendirme | 120/120 sorgu cevaplandı; katalogda olmayanı reddetme 6/6; uydurmama **5/6** |
| Etiket kalitesi | İnsan onaylı etiket **0**; kalite sayıları yalnızca yön gösterir |

## İstek ve maliyet sınırları

| Uç | Sınır |
|---|---|
| Sohbet uçları | dakikada 10 (üye), 5 (anonim), 30 (sunucu) |
| Yeni AI sorusu | Aynı sınır (bu değişiklikle eklendi) + kart başına 5 |
| Tekrar kuyruğu, içe aktarma onayı | İstek başına en çok 5 model çağrısı |
| Not kaydetme | Önemli çıkarım başına 1 çağrı |

## Açık riskler

1. **Orta:** kuyruk, içe aktarma onayı ve not kaydetme uçlarında dakika sınırı yok. Üye bir hesap bunları art arda çağırarak kotayı tüketebilir. Sınır eklenirken büyük içe aktarma bozulmamalı (3000 kayıt = 30 istek); önerilen yol, sınır aşılınca kaydı kabul edip soru üretimini ertelemek.
2. **Orta:** varsayılan sınırlayıcı bellektedir; birden çok süreçte sınır süreç başınadır. Redis sürümü kodda var.
3. **Orta:** Google Cloud tarafında günlük kota ve bütçe uyarısı kodla kurulamaz; sizin kurmanız gerekir.
4. **Hukuki:** ücretsiz katmanda verinin kullanım koşulları farklı olabilir; gizlilik metnindeki ilgili boşluğu kullandığınız plana göre doldurun.
5. **Düşük:** bir "uydurmama" testi başarısız ("book" tek kelimelik sorgu).

## Canlı kontrol listesi

- [ ] Render'da `LLM_API_KEY` silindi
- [ ] Ask AI cevabında kaynak etiketi "Gemini"
- [ ] Deploy logunda `No API key for LLM_PROVIDER` yok
- [ ] Google Cloud'da günlük kota ve bütçe uyarısı var
