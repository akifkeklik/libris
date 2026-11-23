# Render veritabanı güvenlik denetimi

Tarih: 2026-11-24. **Kapsam: kod incelemesi.** Render ortam değişkenleri okunmadı (API erişimi izin katmanında engellendi, zorlanmadı). `DATABASE_URL`'in Render'da tanımlı olup olmadığı bu yüzden **bilinmiyor**; aşağıdaki sonuçlar iki duruma göre yazıldı.

## Kodun davranışı (`backend/container.py`)

| Depo | `DATABASE_URL` tanımlıysa | Tanımlı değilse |
|---|---|---|
| Etkileşimler, notlar, kitap verisi | Doğrudan Postgres bağlantısı | Supabase (okurun JWT'si, RLS) |
| Not tekrarları, kartlar, hatırlatma, içe aktarma, ayarlar | Supabase (JWT, RLS) | Supabase (JWT, RLS) |

## Bulgular

| # | Önem | Bulgu |
|---|---|---|
| 1 | **Yüksek (koşullu)** | `DATABASE_URL` tablo sahibi `postgres` rolüyle tanımlıysa o bağlantıda RLS devre dışıdır. Kullanıcı ayrımı yalnızca `postgres_adapters.py` içindeki `user_id = %s` koşullarına kalır (14 yerde). |
| 2 | Orta (koşullu) | Aynı verinin yarısı doğrudan Postgres'ten, yarısı Supabase üzerinden gider. `DATABASE_URL` başka bir projeyi gösterirse notlar ile kartlar ayrı veritabanlarına yazılır. |
| 3 | Orta | `psycopg2.connect(self._db_uri)` çağrılarında kodda `sslmode` ve `connect_timeout` verilmiyor; URL'de yoksa sürücü varsayılanı geçerli. |
| 4 | Düşük | Depo başına tek bağlantı, havuz yok. |
| 5 | Düşük | Dinamik SQL: `postgres_adapters.py:418` sütun adlarını f-string ile kuruyor; değerler parametreli. Sütun listesinin kod içinde sabit olduğu bu denetimde ayrıca doğrulanmadı. |

## Öneri

1. Render → Environment'ta `DATABASE_URL` **var mı** bakın (değeri kimseyle paylaşmayın).
2. Varsa en basit ve güvenli seçenek **silmek**: uygulama Supabase + RLS yoluna geçer. Önce 09/10/13 uygulanmış olmalı, yoksa notlar çalışmaz.
3. Kalacaksa: tablo sahibi olmayan, en az yetkili bir rol; URL'de `sslmode=require&connect_timeout=10`.
4. `reminder_worker` bu URL'i kullanmaz; kendi gizli anahtarı (`REMINDER_DB_URL`) vardır.

**Doğrulama:** silip deploy ettikten sonra `/api/health/ready` 200 olmalı; test hesabıyla not ekleyip görün. **Geri alma:** değişkeni geri ekleyip yeniden deploy.
