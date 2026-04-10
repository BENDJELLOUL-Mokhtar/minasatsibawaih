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

إذا كنت ستستخدم [index.html](..\index.html) مع خادم `scripts/save_results_server.py` في الوقت نفسه، شغّل تطبيق الويب على منفذ مختلف لتجنّب التعارض:
```powershell
flask --app webapp.app run --port 5050
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
- عند قبول طالب من لوحة المشرف، يُنشئ النظام رابطًا خاصًا لاستمارة الملف الذكي ويرسله إلى بريد الطالب تلقائيًا.
- يمكن للمشرف إعادة إرسال رابط الاستمارة من لوحة المشرف للطلبة المقبولين.
- الحقول الجديدة الخاصة بالاستمارة تُضاف تلقائيًا إلى قاعدة البيانات الحالية عند تشغيل التطبيق أو تنفيذ `init-db`.
- يوفّر التطبيق أيضًا واجهة `GET /api/student-profile?email=...` لتستورد [index.html](..\index.html) بيانات الاستمارة إلى الملف الذكي المحلي.
- صفحة [index.html](..\index.html) تحاول الوصول إلى خادم التسجيل على `http://127.0.0.1:5050` أولاً ثم `http://127.0.0.1:5000`، ويمكن تجاوز ذلك بتحديد `window.MINASAT_WEBAPP_API` أو `localStorage.MINASAT_WEBAPP_API`.
