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
- `SMTP_HOST` — مضيف SMTP (مثال: `smtp.gmail.com` أو `smtp.sendgrid.net`)
- `SMTP_PORT` — المنفذ (مثال: `587`)
- `SMTP_USER` — اسم المستخدم للبريد (أو `apikey` عند استخدام SendGrid SMTP)
- `SMTP_PASS` — كلمة المرور أو مفتاح API
- `MAIL_FROM` — البريد المرسل الظاهر للمستلمين

أمثلة (PowerShell) — استخدام Gmail مع App Password:
```powershell
$env:SMTP_HOST = 'smtp.gmail.com'
$env:SMTP_PORT = '587'
$env:SMTP_USER = 'you@gmail.com'
$env:SMTP_PASS = 'your_app_password'
$env:MAIL_FROM = 'you@gmail.com'
```

أو SendGrid (SMTP relay):
```powershell
$env:SMTP_HOST = 'smtp.sendgrid.net'
$env:SMTP_PORT = '587'
$env:SMTP_USER = 'apikey'
$env:SMTP_PASS = '<SENDGRID_API_KEY>'
$env:MAIL_FROM = 'no-reply@yourdomain.com'
```

اختبار إرسال بريد (بعد تثبيت المتغيرات أعلاه وتشغيل البيئة):
```powershell
# إرسال بريد اختبار
flask --app webapp.app send-test-email recipient@example.com
```

ملاحظات:
- إن لم تُضبط متغيرات SMTP، يعمل النظام في وضع التطوير ويطبع محتوى الرسائل في الـstdout بدلاً من إرسالها فعليًا.
- لتشغيل لوحة المشرف: ادخل إلى `/admin` ثم سجّل الدخول باستخدام `ADMIN_PASSWORD`.

الشهادات (PDF):

- يعتمد توليد شهادات PDF على مكتبة `reportlab`. ثبتها مع الاعتماديات (`pip install -r requirements.txt`).
- لتجسيد نص عربي صحيح قد تحتاج إلى خط TTF يدعم العربية. ضع مسار الملف في متغير البيئة `CERT_FONT_PATH` قبل تشغيل التطبيق، مثال (PowerShell):
```powershell
$env:CERT_FONT_PATH = 'C:\path\to\YourArabicFont.ttf'
``` 
- لتوليد شهادة لنسخة اختبار محفوظة عبر CLI:
```powershell
flask --app webapp.app gen-cert <ATTEMPT_ID>
# مع ارسال بالبريد:
flask --app webapp.app gen-cert <ATTEMPT_ID> --send
```
- عبر واجهة الإدارة: افتح `/admin` → `دفتر الدرجات` ثم استخدم زر "توليد وإرسال" أو زر "تحميل" لتحميل ملف الشهادة.
