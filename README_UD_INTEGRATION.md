# تكامل Universal Dependencies (UD) — قاعدة عربية للاختبارات

ملفاتي المضافة في `scripts/` تساعدك على تحميل شجرة UD العربية، تحويل ملف CoNLL-U إلى قاعدة بيانات SQLite، ثم توليد أسئلة اختيار من متعدد بسيطة من البيانات.

1) تنصيب المتطلبات

افتح Terminal وانتقل إلى مجلد `scripts` ثم أنشئ بيئة افتراضية ونصب الحزم:

```bash
python -m venv .venv
source .venv/bin/activate   # على Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2) تحميل ملف CoNLL-U

مثال (يحمل مجموعة التدريب UD_Arabic-PADT):

```bash
python fetch_ud.py --out ../data/ar_ud_train.conllu
```

يمكنك تبديل `--url` لأي ملف `.conllu` خام آخر.

3) تحويل إلى SQLite

```bash
python parse_conllu_to_sqlite.py --in ../data/ar_ud_train.conllu --out ../data/ud_ar.db
```

هذا يُنشئ قاعدة SQLite تحتوي على جدول `sentences` و `tokens` ببيانات UPOS/FEATS/DEPREL.

4) توليد أسئلة

```bash
python generate_questions.py --db ../data/ud_ar.db --out ../data/ud_questions.json --n 200
```

ستحصل على ملف JSON يحتوي أسئلة بصيغ بسيطة مهيّأة لعرضها أو تحويلها لاحقاً.

ملاحظات وامتدادات مستقبلية:
- يمكنك تحسين مولّد الأسئلة ليصنّف حسب أنواع (POS، Case، DepRel)، أو يولّد أسئلة إعرابية تقليدية (مبتدأ/خبر) عبر قواعد إضافية.
- لنتائج أكثر دقة للنحو العربي التقليدي، دمج مصدر مثل Quranic Arabic Corpus أو نصوص مشكّلة مفيد.
- إذا تريد أدمج المولّد مباشرة ضمن واجهة `index (8).html`، أستطيع كتابة endpoint صغير أو تحويل JSON إلى صيغة JS يمكن للواجهة قراءتها محليًا.
