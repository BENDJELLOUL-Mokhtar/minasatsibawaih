from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import smtplib
from email.message import EmailMessage
from werkzeug.utils import secure_filename
import json
import random
import re
import io
import mimetypes

# optional: reportlab for generating certificate PDFs
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///registrations.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def send_email(to, subject, body):
    """Send email using SMTP if configured, otherwise print to console (dev mode)."""
    MAIL_FROM = os.environ.get('MAIL_FROM', 'no-reply@example.com')
    SMTP_HOST = os.environ.get('SMTP_HOST')
    if not SMTP_HOST:
        # Development: print message instead of sending
        print(f"--- EMAIL (simulated) to={to} subject={subject} ---\n{body}\n")
        return True

    SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
    SMTP_USER = os.environ.get('SMTP_USER')
    SMTP_PASS = os.environ.get('SMTP_PASS')

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = MAIL_FROM
    msg['To'] = to
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            s.starttls()
            if SMTP_USER and SMTP_PASS:
                s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        print('Failed to send email:', e)
        return False


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)
    path = db.Column(db.String(1024), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(300))
    text = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text, nullable=False)  # JSON array
    correct = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Attempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200))
    score = db.Column(db.Integer)
    total = db.Column(db.Integer)
    percent = db.Column(db.Integer)
    details = db.Column(db.Text)  # JSON details of answers
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def extract_text_from_pdf(path):
    """Extract plain text from PDF using PyPDF2. Returns combined text."""
    try:
        from PyPDF2 import PdfReader
    except Exception:
        print('PyPDF2 not installed; PDF extraction not available')
        return ''
    text_parts = []
    try:
        reader = PdfReader(path)
        for p in reader.pages:
            try:
                page_text = p.extract_text() or ''
            except Exception:
                page_text = ''
            text_parts.append(page_text)
    except Exception as e:
        print('PDF extract failed:', e)
    return '\n'.join(text_parts)


def generate_questions_from_text(text, n=10):
    """Improved naive MCQ generator.
    Strategy:
    - split text into sentences
    - pick a reasonably long word from a sentence as the answer
    - choose distractors from the document with similar length
    """
    if not text or text.strip() == '':
        return []
    sentences = re.split(r'(?<=[\.\!\?\؟])\s+', text)
    # words of length >=3 (Arabic letters + word chars)
    words_all = re.findall(r"\b[\wء-ي]{3,}\b", text, flags=re.UNICODE)
    unique_words = list(dict.fromkeys(words_all))
    random.shuffle(sentences)
    questions = []
    # group words by length for distractor selection
    by_len = {}
    for w in unique_words:
        by_len.setdefault(len(w), []).append(w)

    for s in sentences:
        sent_words = re.findall(r"\b[\wء-ي]{3,}\b", s, flags=re.UNICODE)
        # prefer longer words as answers
        sent_words = [w for w in sent_words if len(w) >= 4]
        if not sent_words:
            continue
        answer = max(sent_words, key=lambda x: len(x))
        ans_len = len(answer)

        # collect distractors with similar length
        candidates = []
        for L in range(ans_len - 2, ans_len + 3):
            candidates.extend(by_len.get(L, []))
        candidates = [w for w in candidates if w != answer]
        # prioritize candidates not in the same sentence
        random.shuffle(candidates)
        distractors = []
        for c in candidates:
            if c not in distractors and c != answer:
                distractors.append(c)
            if len(distractors) >= 3:
                break

        # fallback: use other unique words
        i = 0
        while len(distractors) < 3 and i < len(unique_words):
            cand = unique_words[i]
            if cand != answer and cand not in distractors:
                distractors.append(cand)
            i += 1

        opts = [answer] + distractors[:3]
        if len(opts) < 2:
            continue
        # deduplicate and shuffle
        opts = list(dict.fromkeys(opts))
        while len(opts) < 4:
            extra = random.choice(unique_words)
            if extra not in opts and extra != answer:
                opts.append(extra)
        random.shuffle(opts)
        correct_index = opts.index(answer)
        q_text = f"اختر الكلمة الصحيحة في الجملة: «{s.strip()}»"
        questions.append({'q': q_text, 'options': opts, 'correct': correct_index})
        if len(questions) >= n:
            break
    return questions


@app.route('/', methods=['GET', 'POST'])
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role')
        if not name or not email or not role:
            flash('الرجاء تعبئة كل الحقول', 'error')
            return redirect(url_for('register'))

        user = User(name=name, email=email, role=role, status='pending')
        db.session.add(user)
        db.session.commit()

        # Notify applicant that request was received
        send_email(email,
                   'تأكيد استلام طلب التسجيل',
                   f'مرحبًا {name},\n\nتم استلام طلب تسجيلك كـ {role}. سيتحقق المشرف وسيتم إبلاغك عبر البريد بعد اتخاذ القرار.')

        return render_template('thanks.html', name=name)

    return render_template('register.html')


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password and password == os.environ.get('ADMIN_PASSWORD', 'admin'):
            session['is_admin'] = True
            return redirect(url_for('admin'))
        flash('كلمة مرور خاطئة', 'error')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    users = User.query.order_by(User.created_at.desc()).all()
    docs = Document.query.order_by(Document.uploaded_at.desc()).all()
    qcount = Question.query.count()
    return render_template('admin.html', users=users, docs=docs, qcount=qcount)


@app.route('/admin/upload_pdf', methods=['GET', 'POST'])
def upload_pdf():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        f = request.files.get('pdf')
        if not f or f.filename == '':
            flash('لم يتم اختيار ملف', 'error')
            return redirect(url_for('upload_pdf'))
        # ensure upload folder exists inside instance
        upload_folder = os.path.join(app.instance_path, 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        filename = secure_filename(f.filename)
        save_path = os.path.join(upload_folder, filename)
        f.save(save_path)
        doc = Document(filename=filename, path=save_path)
        db.session.add(doc)
        db.session.commit()
        text = extract_text_from_pdf(save_path)
        n = int(request.form.get('n', 10))
        qlist = generate_questions_from_text(text, n=n)
        for q in qlist:
            question = Question(source=filename, text=q['q'], options=json.dumps(q['options'], ensure_ascii=False), correct=q['correct'])
            db.session.add(question)
        db.session.commit()
        flash(f'تم رفع الملف وتوليد {len(qlist)} سؤال', 'success')
        return redirect(url_for('admin'))
    return render_template('upload_pdf.html')


@app.route('/admin/questions')
def admin_questions():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    qs = Question.query.order_by(Question.created_at.desc()).all()
    questions = []
    for q in qs:
        try:
            opts = json.loads(q.options)
        except Exception:
            opts = []
        questions.append({'id': q.id, 'source': q.source, 'text': q.text, 'options': opts, 'correct': q.correct, 'created_at': q.created_at})
    return render_template('questions.html', questions=questions)


@app.route('/admin/grades')
def admin_grades():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    attempts = Attempt.query.order_by(Attempt.created_at.desc()).all()
    parsed = []
    cert_dir = os.path.join(app.instance_path, 'certificates')
    os.makedirs(cert_dir, exist_ok=True)
    for a in attempts:
        try:
            details = json.loads(a.details)
        except Exception:
            details = []
        cert_file = f"certificate_{a.id}.pdf"
        cert_path = os.path.join(cert_dir, cert_file)
        cert_exists = os.path.exists(cert_path)
        parsed.append({'id': a.id, 'email': a.email, 'score': a.score, 'total': a.total, 'percent': a.percent, 'details': details, 'created_at': a.created_at, 'cert_file': cert_file, 'cert_exists': cert_exists})
    return render_template('admin_grades.html', attempts=parsed)


@app.route('/quiz', methods=['GET'])
def quiz():
    n = int(request.args.get('n', 5))
    qs_all = Question.query.all()
    if not qs_all:
        flash('لا توجد أسئلة متاحة حاليا', 'error')
        return redirect(url_for('register'))
    random.shuffle(qs_all)
    selected = qs_all[:n]
    session['quiz_qids'] = [q.id for q in selected]
    questions = []
    for q in selected:
        try:
            opts = json.loads(q.options)
        except Exception:
            opts = []
        questions.append({'id': q.id, 'text': q.text, 'options': opts})
    return render_template('quiz.html', questions=questions)


@app.route('/quiz/submit', methods=['POST'])
def quiz_submit():
    qids = session.pop('quiz_qids', None)
    if not qids:
        flash('جلسة الاختبار انتهت. الرجاء إعادة المحاولة.', 'error')
        return redirect(url_for('quiz'))
    results = []
    correct_count = 0
    for qid in qids:
        q = Question.query.get(qid)
        if not q:
            continue
        try:
            options = json.loads(q.options)
        except Exception:
            options = []
        sel = request.form.get(f'q_{qid}')
        sel_index = int(sel) if (sel is not None and sel != '') else None
        is_correct = (sel_index is not None and sel_index == q.correct)
        if is_correct:
            correct_count += 1
        results.append({'id': q.id, 'text': q.text, 'options': options, 'correct': q.correct, 'selected': sel_index})
    total = len(results)
    percent = int(correct_count / total * 100) if total else 0
    email = request.form.get('email', '').strip()
    email_sent = False
    if email:
        body = f"نتيجة الاختبار: {correct_count}/{total} ({percent}%)\n\nالتفاصيل:\n"
        for r in results:
            sel_text = r['options'][r['selected']] if (r['selected'] is not None and r['selected'] < len(r['options'])) else 'لا إجابة'
            correct_text = r['options'][r['correct']] if (r['correct'] is not None and r['correct'] < len(r['options'])) else '—'
            body += f"- {r['text']}\n  إجابتك: {sel_text} | الصحيح: {correct_text}\n"
        email_sent = send_email(email, 'نتيجة الاختبار', body)
        if email_sent:
            flash('أُرسلت النتيجة إلى البريد (إن كان صالحاً).', 'info')
        else:
            flash('فشل إرسال النتيجة إلى البريد.', 'error')
    # Save attempt to DB
    try:
        attempt = Attempt(email=email if email else None,
                          score=correct_count,
                          total=total,
                          percent=percent,
                          details=json.dumps(results, ensure_ascii=False))
        db.session.add(attempt)
        db.session.commit()
    except Exception as e:
        print('Failed to save attempt:', e)
    return render_template('quiz_result.html', results=results, score=correct_count, total=total, percent=percent, email=email, email_sent=email_sent)


@app.route('/admin/approve/<int:user_id>', methods=['POST'])
def approve(user_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    user = User.query.get_or_404(user_id)
    user.status = 'approved'
    db.session.commit()
    send_email(user.email, 'قرار التسجيل: قبول', f'مرحبًا {user.name},\n\nتم قبول طلب تسجيلك كـ {user.role}.')
    flash('تم قبول الطلب وإرسال إشعار للمستخدم', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/reject/<int:user_id>', methods=['POST'])
def reject(user_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    user = User.query.get_or_404(user_id)
    user.status = 'rejected'
    db.session.commit()
    send_email(user.email, 'قرار التسجيل: رفض', f'مرحبًا {user.name},\n\nعذراً، تم رفض طلب تسجيلك.')
    flash('تم رفض الطلب وإشعار المستخدم', 'info')
    return redirect(url_for('admin'))


@app.cli.command('init-db')
def init_db():
    """Create database tables."""
    db.create_all()
    print('Database initialized.')

import click

@app.cli.command('send-test-email')
@click.argument('to')
def send_test_email(to):
    """Send a test email to the given address using configured SMTP."""
    ok = send_email(to, 'اختبار البريد', 'هذه رسالة اختبار من نظام التسجيل.')
    if ok:
        print('Test email sent to', to)
    else:
        print('Failed to send test email to', to)


@app.cli.command('import-doc')
@click.argument('path')
@click.option('--n', default=20, help='Number of questions to generate')
def import_doc(path, n):
    """Import a local text or PDF file and generate questions from it."""
    p = os.path.abspath(path)
    if p.lower().endswith('.pdf'):
        text = extract_text_from_pdf(p)
    else:
        with open(p, 'r', encoding='utf-8') as f:
            text = f.read()
    filename = os.path.basename(p)
    doc = Document(filename=filename, path=p)
    db.session.add(doc)
    db.session.commit()
    qlist = generate_questions_from_text(text, n=n)
    for q in qlist:
        question = Question(source=filename, text=q['q'], options=json.dumps(q['options'], ensure_ascii=False), correct=q['correct'])
        db.session.add(question)
    db.session.commit()
    print(f'Imported {len(qlist)} questions from {filename}')


def certificate_dir():
    p = os.path.join(app.instance_path, 'certificates')
    os.makedirs(p, exist_ok=True)
    return p


def generate_certificate_pdf(attempt):
    """Generate a simple PDF certificate for the given Attempt and return (path, filename)."""
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError('reportlab not installed; install reportlab in your environment')
    certpath = certificate_dir()
    filename = f"certificate_{attempt.id}.pdf"
    path = os.path.join(certpath, filename)

    # Determine recipient name (try to find a User by email)
    name = None
    if attempt.email:
        user = User.query.filter_by(email=attempt.email).first()
        if user:
            name = user.name
    name = name or (attempt.email or f'Attempt {attempt.id}')

    # register font if provided (use CERT_FONT_PATH env var)
    font_name = 'Helvetica'
    font_path = os.environ.get('CERT_FONT_PATH')
    if font_path and os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('CertFont', font_path))
            font_name = 'CertFont'
        except Exception as e:
            print('Failed to register cert font:', e)

    c = canvas.Canvas(path, pagesize=landscape(A4))
    w, h = landscape(A4)

    # border
    c.setLineWidth(4)
    c.rect(30, 30, w-60, h-60)

    # Title
    c.setFont(font_name, 36)
    c.drawCentredString(w/2, h-140, 'شهادة إتمام')

    # Recipient name
    c.setFont(font_name, 28)
    c.drawCentredString(w/2, h/2 + 20, str(name))

    # Score details
    info = f"نتيجة الاختبار: {attempt.score}/{attempt.total} — النسبة: {attempt.percent}%"
    c.setFont(font_name, 14)
    c.drawCentredString(w/2, h/2 - 20, info)

    # Footer / issuer
    issued = datetime.utcnow().strftime('%Y-%m-%d')
    c.setFont(font_name, 12)
    c.drawString(60, 60, f'تاريخ الإصدار: {issued}')
    c.drawRightString(w-60, 60, 'نظام التقييم')

    c.showPage()
    c.save()
    return path, filename


def send_email_with_attachment(to, subject, body, attachment_path):
    MAIL_FROM = os.environ.get('MAIL_FROM', 'no-reply@example.com')
    SMTP_HOST = os.environ.get('SMTP_HOST')
    if not SMTP_HOST:
        print(f"--- EMAIL (simulated) to={to} subject={subject} attachment={attachment_path} ---\n{body}\n")
        return True
    SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
    SMTP_USER = os.environ.get('SMTP_USER')
    SMTP_PASS = os.environ.get('SMTP_PASS')

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = MAIL_FROM
    msg['To'] = to
    msg.set_content(body)

    try:
        with open(attachment_path, 'rb') as af:
            data = af.read()
            maintype, subtype = 'application', 'pdf'
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=os.path.basename(attachment_path))
    except Exception as e:
        print('Failed to attach file:', e)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            s.starttls()
            if SMTP_USER and SMTP_PASS:
                s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        print('Failed to send email with attachment:', e)
        return False


@app.route('/certificates/<path:filename>')
def download_certificate(filename):
    # serve certificate files from instance/certificates
    p = certificate_dir()
    return send_from_directory(p, filename, as_attachment=True)


@app.route('/admin/cert/generate/<int:attempt_id>', methods=['POST'])
def admin_generate_certificate(attempt_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    a = Attempt.query.get_or_404(attempt_id)
    try:
        path, fname = generate_certificate_pdf(a)
    except Exception as e:
        flash('فشل إنشاء الشهادة: ' + str(e), 'error')
        return redirect(url_for('admin_grades'))
    send_it = request.form.get('send') == '1' or request.form.get('send') == 'on' or request.form.get('send') == 'true'
    if send_it and a.email:
        ok = send_email_with_attachment(a.email, 'شهادة الاختبار', 'مرفق شهادة إتمام الاختبار.', path)
        if ok:
            flash('تم توليد الشهادة وإرسالها عبر البريد', 'success')
        else:
            flash('تم توليد الشهادة لكن فشل إرسالها', 'error')
    else:
        flash('تم توليد الشهادة', 'success')
    return redirect(url_for('admin_grades'))


@app.cli.command('gen-cert')
@click.argument('attempt_id', type=int)
@click.option('--send', is_flag=True, help='Send certificate by email')
def gen_cert(attempt_id, send):
    """Generate a certificate for an attempt and optionally email it."""
    with app.app_context():
        a = Attempt.query.get(attempt_id)
        if not a:
            print('Attempt not found')
            return
        path, fname = generate_certificate_pdf(a)
        print('Generated:', path)
        if send and a.email:
            ok = send_email_with_attachment(a.email, 'شهادة الاختبار', 'مرفق شهادة الإتمام', path)
            print('Sent:', ok)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
