# AI Canlı Değerlendirme Raporu

**Durum: COMPLETED** (120/120 sorgu + 12 adversarial; çalışma sonuna kadar tamamlandı)
**Çalıştırma:** 2026-11-22 00:14 → 00:24 (607 sn) · commit `6ab1e6a` · `python -m backend.scripts.run_rag_quality_eval run --dataset all --pause 1.0`
**Ortam:** yerel backend, gerçek Gemini (`gemini-3.5-flash-lite`, `models/gemini-embedding-2`), production Supabase'e yalnızca okuma (vector RPC). Veritabanına hiçbir şey yazılmadı. Değerlendirme setinde kullanıcı verisi yok: sorgular sentetik, katalog herkese açık kitap verisi.
**Ham çıktılar:**
- `backend/evaluation/reports/rag_quality_eval.{json,md}`
- `rag_quality_eval_queries.csv` (sorgu başına satır)
- `rag_live_analysis.json` (bu rapordaki ek analiz; `python -m backend.scripts.analyze_live_rag_eval` ile tekrar üretilir, offline)

## 0. Etiketler hakkında (önce okuyun)

| Etiket katmanı | Sorgu | Kaynak | Güvenilirlik |
|---|---|---|---|
| `rule_derived` | 19 | Kimlik kuralları (yazar/başlık eşleşmesi) | En güvenilir; seçim kararlarında kullanılabilir |
| `proposed` | 21 | Elle önerilmiş, **insan tarafından gözden geçirilmemiş** | Yalnızca yönlendirme amaçlı |
| `automatic_candidate` | 60 | **Otomatik** (kurallarla aday üretimi) | Zayıf; yön göstergesi |
| Davranış ölçümü (etiketsiz) | 20 | abstain / no-fabrication / open | Pass/fail kontrolleri |

**İnsan tarafından doğrulanmış relevance etiketi: 0.** Bu rapordaki hiçbir sayı insan onaylı kalite ölçümü değildir. Bu koşuda yeni ortaya çıkan 1.132 (sorgu, kitap) çifti `data/rag_eval_judgments.csv` dosyasına **inceleme kuyruğu** olarak eklendi; bu çiftler not verilmemiş halde duruyor.

## 1. Maliyet ve limitler (ölçülen)

| Kalem | Tahmin (önceki rapor) | Gerçekleşen |
|---|---|---|
| Generate çağrısı | ~150 | **132** (131 × 200, 1 × 503) |
| Embed çağrısı | ~135 | **134** (131 × 200, 3 × 429) |
| Toplam HTTP çağrısı | ~285 | **266** |
| Generate token | ~190k | **167.147** (prompt 137.467 + çıktı 29.680; çağrı başına ortalama 1.276) |
| Embed token | – | 1.153 |
| Süre | 20–30 dk | **10 dk 7 sn** |

- **Rate limit:** 3 embed çağrısı 429 aldı. Bunların 2'si istemcinin tek retry'ı ile kurtuldu; 1'i kurtulamadı ve o sorgu dürüstçe degraded olarak etiketlendi (bölüm 3).
- **Koruma:** 5 rate-limit hatasında çalışmayı durduran bir guard vardı; tetiklenmedi.
- **Ek retry yok:** İstemcinin 1 retry'ı dışında yeniden deneme yapılmadı.
- **Fatura:** Ücret plana bağlı olduğu için hesaplanmadı; token sayıları yukarıda.

## 2. Retrieval metrikleri (production cevabı, ilk 5 kitap)

| Katman | n | Hit@5 | P@5 | R@5 | MRR@5 | nDCG@5 |
|---|---|---|---|---|---|---|
| **rule_derived** | 19 | 1.000 | 0.474 | **0.979** | 1.000 | **0.982** |
| proposed | 21 | 0.952 | 0.457 | 0.586 | 0.786 | 0.605 |
| automatic_candidate | 60 | 0.883 | 0.410 | 0.703 | 0.717 | 0.661 |

- P@5'in üst sınırı, ilgili kitap sayısı 5'ten azsa 1 değildir. rule_derived sorgularda ilgili set genellikle 2–3 kitaptır; bu yüzden P@5 ≈ 0,47 ile R@5 ≈ 0,98 birlikte "neredeyse tamamı bulundu" anlamına gelir.
- Dil bazında (rule_derived): EN nDCG@5 0.979, TR (Türkçe harflerle) 0.979, TR (ASCII yazımla) 1.000. **Türkçe ve İngilizce eşit.**

### Önceki canlı koşuyla karşılaştırma (aynı 40 sorgu)

| Katman | Metrik | 2026-11-21 14:47 | 2026-11-22 00:24 |
|---|---|---|---|
| rule_derived (19) | production nDCG@5 | 0.958 | **0.982** |
| rule_derived (19) | production R@5 | 0.947 | 0.979 |
| proposed (21) | production nDCG@5 | 0.474 | 0.605 |
| rule_derived (19) | semantic stage (RPC) nDCG@5 | 0.965 | 0.965 (aynı) |

**Yorum:** Semantic retrieval aşaması birebir aynı; fark yalnızca production'ın ilk 5 sıralamasında. Bu, iki koşu arasında yapılan "seed'siz semantic sorgularda MMR yok" değişikliğiyle tutarlı. O değişikliğin offline tahmini rule_derived'da +0,031 [+0,007, +0,061] idi; canlı ölçüm +0,024 ve bu aralığın içinde. Önceki koşu commit kaydetmediği için bu yorum bir **çıkarımdır**. Proposed etiketlerdeki artış yalnızca yön göstergesidir.

### Kategori bazında (tüm katmanlar karışık)

| Kategori | n | Hit@5 | nDCG@5 |
|---|---|---|---|
| author | 15 | 1.00 | 0.977 |
| exact_title | 17 | 1.00 | 0.945 |
| semantic_description | 17 | 1.00 | 0.913 |
| topic | 15 | 1.00 | 0.678 |
| similar | 14 | 0.93 | 0.530 |
| genre | 12 | 1.00 | 0.505 |
| mood | 4 | 0.50 | 0.245 |
| **multi_constraint** | 6 | **0.17** | **0.022** |

## 3. Güvenilirlik

| Metrik | Değer |
|---|---|
| Gemini cevabı (`source = rag_llm`) | **120 / 120** |
| LLM fallback oranı (`grounded_fallback`) | **0 %** |
| Degraded retrieval | **1 / 120 (0,8 %)**: `open_sad_en`, embedding 429 sonrası `lexical_fallback`. `status=lexical_fallback`, `degraded=true` olarak etiketlendi ve cache'lenmedi; başarı gibi raporlanmadı. |
| Gemini generate HTTP hata oranı | 1 / 132 = **0,76 %** (503; retry ile kurtuldu) |
| Gemini embed HTTP hata oranı | 3 / 134 = **2,24 %** (429) |
| Context'in prompt'a ulaşması | 100 % |
| Cevapta yabancı ISBN | 0 |
| Cevapta katalog dışı başlık | 0 |
| Cevapta context dışı yazar adı | 3 (`unsupported_claim_rate` 2,5 %) |
| Yanlış dilde cevap | 3: `genre_cooking_en`, `title_fahrenheit_en`, `title_fahrenheit_tr` |
| Adversarial set (injection, false premise, kurgusal başlık/yazar, alan dışı) | **12 / 12 geçti** |
| Katalogda olmayanı reddetme (`abstain_not_in_catalog`) | 6 / 6 |
| Uydurmama (`no_fabrication`) | 5 / 6; başarısız: `insuff_one_word_en` ("book"), cevapta context dışı bir yazar adı var |

## 4. Gecikme (soğuk istek, n = 120)

| Aşama | p50 | p95 | max |
|---|---|---|---|
| Query embedding | 435 ms | 535 ms | 1.211 ms |
| Vector RPC | 249 ms | 619 ms | 1.408 ms |
| **Gemini generation** | **1.098 ms** | **1.764 ms** | 3.023 ms |
| **Uçtan uca** | **2.490 ms** | **3.330 ms** | 4.653 ms |
| Cache'ten (aynı sorgu tekrar) | 0,4 ms | 0,8 ms | – |

Önceki koşuda generation p50 5,2 sn ve p95 15 sn idi. Aradaki fark büyük ölçüde Gemini tarafındaki yük ve zamanla ilgili olabilir; kod değişikliğine **atfedilmedi**. Gecikme dağılımı, saate bağlı olarak böyle oynayabiliyor.

## 5. Çeşitlilik ve kapsam

| Metrik | Değer |
|---|---|
| Liste içi farklı birincil kategori oranı (ilk 5, ortalama) | 0.543 |
| Liste içi farklı ilk yazar oranı (ilk 5, ortalama) | 0.705 |
| Gösterilen farklı kitap | 307 (600 slotta) |
| Katalog kapsamı | 307 / 6.446 = **4,8 %** |

Yazar sorgularında aynı yazarın tekrar etmesi doğru davranıştır, bu yüzden yazar çeşitliliği orada beklenen şekilde düşük çıkıyor.

**En çok tekrar eden kitaplar** (120 sorguda):

| Kitap | Sorgu sayısı |
|---|---|
| The Shadow of the Wind | **10** |
| The Handmaid's Tale | 7 |
| The Shining | 7 |
| Brave New World and Brave New World Revisited | 6 |
| Nightmares and Dreamscapes | 6 |
| The Murder of Roger Ackroyd | 6 |
| The Gods Themselves | 6 |
| The Foundation Trilogy | 5 |
| The Diamond Age | 5 |
| 1984 | 5 |

*The Shadow of the Wind*'in 10 farklı sorguda çıkması (çoğu tür veya ruh hali sorgusu) bir **popülerlik ya da "hub" etkisine** işaret ediyor. Bu kategori dışı önerilerin olası bir kaynağı; nedeni ölçülmedi.

## 6. En başarılı ve en başarısız sorgular (production nDCG@5; 100 skorlanan sorgu)

**En başarılı 10** (hepsi 1.000; eşitlikte alfabetik): `author_asimov_en/tr`, `author_christie_en/tr/tr_ascii`, `author_king_en/tr`, `author_orwell_en/tr`, `author_pratchett_en`. Ayrıca başlık ve tanım sorgularının çoğu 1.000.

**En başarısız 10:**

| Sorgu | Kategori | Etiket | nDCG@5 |
|---|---|---|---|
| mood_funny_en / _tr | mood | automatic | 0.000 |
| multi_history_recent_en / _tr | multi_constraint | automatic | 0.000 |
| multi_king_short_en / _tr | multi_constraint | automatic | 0.000 |
| multi_poetry_short_en | multi_constraint | automatic | 0.000 |
| sim_dune_en | similar | proposed | 0.000 |
| genre_scifi_tr | genre | automatic | 0.131 |
| multi_poetry_short_tr | multi_constraint | automatic | 0.131 |

**Teşhis:**
- **Çok kısıtlı sorgular** ("kısa bir Stephen King romanı", "yakın tarihli bir tarih kitabı") sistemli olarak başarısız. Semantic arama sayfa sayısı ve yayın yılı gibi yapısal kısıtları uygulamıyor. Bu kategori bir **yetenek eksiği**; etiket gürültüsü değil.
- "Dune gibi kitaplar" sorgusunda Dune'un kendisi katalogda yok. Cevap bunu açıkça söylüyor (uydurma yok), ama önerilen kitaplar proposed etiket setiyle örtüşmüyor.

## 7. Çapraz analiz

**Retrieval iyi, LLM cevabı sorunlu (6):**

| Sorgu | Sorun | nDCG@5 |
|---|---|---|
| title_fahrenheit_en / _tr | Yanlış dilde cevap | 1.00 / 0.63 |
| genre_cooking_en | Yanlış dilde cevap | 0.79 |
| genre_poetry_en | Context dışı yazar adı | 0.68 |
| multi_king_short_en | Context dışı yazar adı (retrieval da zayıf) | 0.00 |
| insuff_one_word_en | Context dışı yazar adı | (etiketsiz) |

**LLM cevap verdi, retrieval zayıf (nDCG@5 < 0,3):** 15 sorgu: multi_constraint ×6, mood ×2, similar ×3, genre ×2 ve topic_wwii ×2. Bunlarda Gemini kibarca ve grounded cevap veriyor, ama getirilen kitaplar etikete uymuyor. Kullanıcı için en riskli grup bu, çünkü cevap güven verici görünürken kitaplar isteğe uymuyor.

## 8. Sonuç ve öneriler

1. **Gemini canlı cevap üretebiliyor:** 120/120, %0 LLM fallback, p95 1,8 sn. Bu sonuç **yerel** ortamda alındı; production'daki 401 ayrı bir konfigürasyon sorunu (bkz. `GEMINI_PRODUCTION_READINESS.md`).
2. Kimlik sorgularında (yazar, başlık, tanım) kalite yüksek ve TR/EN eşit.
3. Zayıf alanlar: çok kısıtlı sorgular, ruh hali, "benzer kitap" sorguları ve popüler kitap tekrarları. Öneri: yapısal kısıtların (sayfa, yıl, yazar) retrieval sonrası filtre olarak uygulanması ve tekrar eden kitaplar için bir "hub" cezası. Her ikisi de önce offline harness ile ölçülmeli. **Bu koşuda uygulanmadı.**
4. Yanlış dil (3) ve context dışı yazar adı (3) için prompt kuralları sıkılaştırılabilir. Etkisi yeniden canlı ölçülmeden iyileşme iddia edilmemeli.
5. Kalite iddialarını güçlendirmek için `data/rag_eval_judgments.csv` inceleme kuyruğunun insan tarafından notlanması gerekiyor (`evaluation/REVIEW_GUIDE.md`).
