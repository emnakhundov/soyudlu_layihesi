# Söyüdlü ESD – Enterprise Service Desk & Fleet Maintenance

Flask + SQLAlchemy (SQLite) əsaslı avtomobil parkı və təmir idarəetmə sistemi.

## İlkin administrator

| Sahə | Dəyər |
|------|-------|
| İstifadəçi adı | `admin` |
| Müvəqqəti parol | `Soyudlu@2026!Admin` (`.env`-də `ADMIN_PASSWORD` ilə dəyişdirilir) |

İlk girişdə sistem parol dəyişdirməyi, sonra 2FA (Microsoft/Google Authenticator) quraşdırmağı tələb edir.
Quraşdırmadan sonra 10 bərpa kodu göstərilir – onları saxlayın.

## Windows

`start_windows.bat` faylını işə salın. Virtual mühit yaradır, asılılıqları quraşdırır, `.env` yaradır, bazanı hazırlayır və serveri başladır.
Brauzerdə: http://127.0.0.1:5000

## Linux (lokal)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # SECRET_KEY-i mütləq dəyişdirin
python run.py init-db
python run.py                 # və ya: gunicorn --bind 0.0.0.0:8000 --workers 3 --threads 2 wsgi:app
```

## Docker

```bash
cp .env.example .env
docker compose up -d --build
```

HTTPS arxasında işləyirsinizsə `.env`-də `SESSION_COOKIE_SECURE=1` təyin edin.

## Modullar

- **Autentifikasiya:** Argon2 parol hash-ı, parol siyasəti, məcburi ilk parol dəyişikliyi, TOTP 2FA (eyni 30 saniyəlik kodun təkrar istifadəsinin qarşısı alınır), bərpa kodları, uğursuz cəhdlərə görə müvəqqəti bloklama, sessiya vaxt aşımı.
- **RBAC:** Super Admin, Administrator, Dispetçer, Təmir mühəndisi, Təmir texniki, Nəzarətçi, İzləyici; yeni rol yaratmaq və istifadəçiyə rol təyin etmək.
- **Avtomobillər:** əlavə etmək, siyahı, təmir tarixçəsi.
- **Təmir iş axını:** Yeni → Təyin edildi → Təmirdə / Gözləmədə → Tamamlandı → Təsdiqləndi, və ya rədd edildikdə yenidən Təmirdə. Hər mərhələdə icazə yoxlanır.
- **Bildirişlər:** daxili bildiriş mərkəzi (`app/routes/repairs.py` içindəki `_notify` funksiyası SMTP/Teams üçün genişləndirilə bilər).
- **Audit jurnalı:** giriş/çıxış, uğursuz cəhdlər, icazə rədləri, istifadəçi/rol dəyişiklikləri, təmir addımları. Yalnız oxunur.
- **Hesabat:** təmir müraciətlərinin CSV ixracı (Excel üçün UTF-8 BOM ilə).

## Test siyahısı (öz mühitinizdə)

1. `admin` / ilkin parolla daxil olun → parol dəyişdirmə səhifəsi açılmalıdır.
2. Yeni parol → 2FA QR səhifəsi → Authenticator-dən kodu daxil edin → bərpa kodları göstərilməlidir.
3. Çıxış edin, yenidən daxil olun → username + parol + 6 rəqəm tələb olunmalıdır.
4. Eyni TOTP kodunu iki dəfə istifadə etməyə çalışın → ikinci dəfə rədd edilməlidir.
5. Yanlış parolu 5 dəfə yazın → hesab 15 dəqiqə bloklanmalıdır.
6. Admin paneldən yeni istifadəçi yaradın, rol təyin edin; həmin istifadəçi ilə giriş edib icazəsiz səhifələrə (məs. `/admin/audit`) girişin 403 olduğunu yoxlayın.
7. Dispetçer müraciət yaradır → Təmir mühəndisi təyin edir → texnik işi yeniləyir və tamamlayır → mühəndis təsdiq və ya rədd edir; hər addımda bildirişlər düşməlidir.
8. `/repairs/export.csv` faylının açılması.

## Məhdudiyyətlər (açıq şəkildə)

- Avtomobil redaktəsi, şöbə/şirkət cədvəlləri, sessiya siyahısı (`user_sessions`) və ehtiyat hissə kataloqu bu versiyada yoxdur.
- Fayl yükləmə (foto sübutu) yoxdur.
- Bildirişlər yalnız daxili mərkəzdədir; e-poçt/Teams göndərilmir.
- Sxem dəyişiklikləri üçün Alembic miqrasiyası yoxdur; `db.create_all()` yalnız yeni cədvəlləri yaradır.
- Standart administrator parolu ilk girişdə dəyişdirilməlidir; production-da `SECRET_KEY` və `ADMIN_PASSWORD` mütləq dəyişdirilməlidir.
