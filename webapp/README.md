# Webapp — نظام تسجيل بسيط

تشغيل محلي (تفترض وجود Python 3):

1. إنشاء بيئة:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
2. تهيئة قاعدة البيانات:
```powershell
flask --app webapp.app init-db
```
3. تشغيل التطبيق:
```powershell
flask --app webapp.app run
```

إعداد متغيرات البيئة المهمة:
- `ADMIN_PASSWORD` — كلمة مرور دخول المشرف (افتراضي: `admin`)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `MAIL_FROM` — إعدادات البريد (اختياري). إن لم توفَّر، تُطبَع الرسائل بدل إرسالها.
