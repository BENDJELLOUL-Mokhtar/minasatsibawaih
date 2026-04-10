from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import inspect, text
import json
import os
import secrets
import smtplib
from email.message import EmailMessage

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
    profile_form_token = db.Column(db.String(120), nullable=True)
    profile_form_status = db.Column(db.String(30), default='awaiting_approval')
    profile_form_data = db.Column(db.Text, nullable=True)
    profile_form_sent_at = db.Column(db.DateTime, nullable=True)
    profile_form_submitted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def ensure_user_schema():
    """Add newly introduced profile-form columns when the database already exists."""
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        if 'user' not in inspector.get_table_names():
            return

        existing = {col['name'] for col in inspector.get_columns('user')}
        statements = []
        if 'profile_form_token' not in existing:
            statements.append("ALTER TABLE user ADD COLUMN profile_form_token VARCHAR(120)")
        if 'profile_form_status' not in existing:
            statements.append("ALTER TABLE user ADD COLUMN profile_form_status VARCHAR(30) DEFAULT 'awaiting_approval'")
        if 'profile_form_data' not in existing:
            statements.append("ALTER TABLE user ADD COLUMN profile_form_data TEXT")
        if 'profile_form_sent_at' not in existing:
            statements.append("ALTER TABLE user ADD COLUMN profile_form_sent_at DATETIME")
        if 'profile_form_submitted_at' not in existing:
            statements.append("ALTER TABLE user ADD COLUMN profile_form_submitted_at DATETIME")

        if statements:
            with db.engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))
                connection.execute(text(
                    "UPDATE user SET profile_form_status='awaiting_approval' "
                    "WHERE role='student' AND (profile_form_status IS NULL OR profile_form_status='')"
                ))


def empty_profile_form_payload():
    return {
        'socialIntegration': '',
        'culturalExposure': '',
        'economicLevel': '',
        'familySupport': '',
        'familyStructure': '',
        'housingType': '',
        'studySpace': '',
        'birthOrder': '',
        'brothersCount': '',
        'sistersCount': '',
        'homeLanguage': '',
        'devicesAccess': '',
        'internetAccess': '',
        'workCommitment': '',
        'socialConsent': False,
        'socialAccounts': {
            'facebook': '',
            'instagram': '',
            'x': '',
            'tiktok': '',
            'youtube': '',
            'telegram': '',
            'whatsapp': '',
            'linkedin': '',
        },
        'notes': '',
        'submittedAt': '',
    }


def normalize_profile_number(value):
    raw = (value or '').strip()
    if not raw:
        return ''
    try:
        number = int(raw)
    except ValueError:
        return ''
    return str(number if number >= 0 else 0)


def load_profile_form_payload(user):
    payload = empty_profile_form_payload()
    raw = user.profile_form_data or ''
    if not raw:
        return payload
    try:
        parsed = json.loads(raw)
    except Exception:
        return payload
    if not isinstance(parsed, dict):
        return payload

    payload.update({
        key: parsed.get(key, payload[key])
        for key in payload.keys()
        if key != 'socialAccounts'
    })
    accounts = parsed.get('socialAccounts') or {}
    if not isinstance(accounts, dict):
        accounts = {}
    payload['socialAccounts'] = {**payload['socialAccounts'], **accounts}
    payload['socialConsent'] = bool(payload.get('socialConsent'))
    payload['birthOrder'] = normalize_profile_number(payload.get('birthOrder'))
    payload['brothersCount'] = normalize_profile_number(payload.get('brothersCount'))
    payload['sistersCount'] = normalize_profile_number(payload.get('sistersCount'))
    return payload


def extract_profile_form_payload(form):
    return {
        'socialIntegration': form.get('socialIntegration', '').strip(),
        'culturalExposure': form.get('culturalExposure', '').strip(),
        'economicLevel': form.get('economicLevel', '').strip(),
        'familySupport': form.get('familySupport', '').strip(),
        'familyStructure': form.get('familyStructure', '').strip(),
        'housingType': form.get('housingType', '').strip(),
        'studySpace': form.get('studySpace', '').strip(),
        'birthOrder': normalize_profile_number(form.get('birthOrder')),
        'brothersCount': normalize_profile_number(form.get('brothersCount')),
        'sistersCount': normalize_profile_number(form.get('sistersCount')),
        'homeLanguage': form.get('homeLanguage', '').strip(),
        'devicesAccess': form.get('devicesAccess', '').strip(),
        'internetAccess': form.get('internetAccess', '').strip(),
        'workCommitment': form.get('workCommitment', '').strip(),
        'socialConsent': bool(form.get('socialConsent')),
        'socialAccounts': {
            'facebook': form.get('socialFacebook', '').strip(),
            'instagram': form.get('socialInstagram', '').strip(),
            'x': form.get('socialX', '').strip(),
            'tiktok': form.get('socialTiktok', '').strip(),
            'youtube': form.get('socialYoutube', '').strip(),
            'telegram': form.get('socialTelegram', '').strip(),
            'whatsapp': form.get('socialWhatsapp', '').strip(),
            'linkedin': form.get('socialLinkedin', '').strip(),
        },
        'notes': form.get('notes', '').strip(),
        'submittedAt': datetime.utcnow().isoformat() + 'Z',
    }


def generate_profile_form_token():
    while True:
        token = secrets.token_urlsafe(24)
        if not User.query.filter_by(profile_form_token=token).first():
            return token


def ensure_student_profile_form(user):
    if user.role != 'student':
        return None
    if not user.profile_form_token:
        user.profile_form_token = generate_profile_form_token()
    if not user.profile_form_status or user.profile_form_status == 'awaiting_approval':
        user.profile_form_status = 'sent'
    user.profile_form_sent_at = datetime.utcnow()
    return user.profile_form_token


def build_student_profile_form_link(token):
    return url_for('student_profile_form', token=token, _external=True)


def send_student_profile_form_email(user, form_link, is_resend=False):
    subject = 'استكمال الملف الذكي للطالب' if is_resend else 'قبول الطلب واستكمال الملف الذكي'
    intro = 'أُعيد إرسال الرابط لك' if is_resend else 'تم قبول طلب تسجيلك'
    body = (
        f'مرحبًا {user.name},\n\n'
        f'{intro} على المنصة. لإتمام بياناتك الثقافية والاجتماعية والأسرية عبر الاستبيان، '
        f'يرجى فتح الرابط التالي وتعبئة النموذج:\n\n{form_link}\n\n'
        'يمكنك تعديل إجاباتك لاحقًا عبر الرابط نفسه ما دام صالحًا.\n\n'
        'مع التقدير.'
    )
    return send_email(user.email, subject, body)


def profile_form_status_label(status):
    return {
        'awaiting_approval': 'بانتظار القبول',
        'sent': 'أُرسل الرابط',
        'submitted': 'أُرسلت الإجابات',
    }.get(status or '', 'غير متاح')


def serialize_student_profile_sync(user):
    return {
        'name': user.name,
        'email': user.email,
        'profileFormStatus': user.profile_form_status,
        'profileFormSubmittedAt': user.profile_form_submitted_at.isoformat() + 'Z' if user.profile_form_submitted_at else '',
        'smartProfile': load_profile_form_payload(user),
    }


ensure_user_schema()


@app.after_request
def add_api_cors_headers(response):
    if request.path.startswith('/api/'):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


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

        profile_form_status = 'awaiting_approval' if role == 'student' else None
        user = User(name=name, email=email, role=role, status='pending', profile_form_status=profile_form_status)
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
    return render_template('admin.html', users=users, profile_form_status_label=profile_form_status_label)


@app.route('/admin/approve/<int:user_id>', methods=['POST'])
def approve(user_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    user = User.query.get_or_404(user_id)
    user.status = 'approved'
    profile_link = None
    if user.role == 'student':
        token = ensure_student_profile_form(user)
        profile_link = build_student_profile_form_link(token)
    db.session.commit()
    if user.role == 'student':
        sent = send_student_profile_form_email(user, profile_link)
        if sent:
            flash('تم قبول الطلب وإرسال رابط استبيان الملف الذكي للطالب', 'success')
        else:
            flash('تم قبول الطلب، لكن تعذّر إرسال رابط الاستبيان عبر البريد', 'info')
    else:
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


@app.route('/admin/send-profile-form/<int:user_id>', methods=['POST'])
def send_profile_form(user_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    user = User.query.get_or_404(user_id)
    if user.role != 'student' or user.status != 'approved':
        flash('هذا الإجراء متاح للطلبة المقبولين فقط', 'error')
        return redirect(url_for('admin'))

    token = ensure_student_profile_form(user)
    profile_link = build_student_profile_form_link(token)
    db.session.commit()
    sent = send_student_profile_form_email(user, profile_link, is_resend=True)
    if sent:
        flash('تمت إعادة إرسال رابط استمارة الملف الذكي', 'success')
    else:
        flash('تعذّر إرسال رابط استمارة الملف الذكي', 'error')
    return redirect(url_for('admin'))


@app.route('/profile-form/<token>', methods=['GET', 'POST'])
def student_profile_form(token):
    user = User.query.filter_by(profile_form_token=token, role='student').first_or_404()
    if user.status != 'approved':
        flash('هذا الرابط غير مفعل بعد. انتظر اعتماد التسجيل أولاً.', 'error')
        return redirect(url_for('register'))

    data = load_profile_form_payload(user)
    if request.method == 'POST':
        payload = extract_profile_form_payload(request.form)
        user.profile_form_data = json.dumps(payload, ensure_ascii=False)
        user.profile_form_status = 'submitted'
        user.profile_form_submitted_at = datetime.utcnow()
        db.session.commit()
        return redirect(url_for('student_profile_form_done', token=token))

    return render_template(
        'profile_form.html',
        user=user,
        data=data,
        already_submitted=user.profile_form_status == 'submitted'
    )


@app.route('/profile-form/<token>/done')
def student_profile_form_done(token):
    user = User.query.filter_by(profile_form_token=token, role='student').first_or_404()
    return render_template('profile_form_done.html', user=user)


@app.route('/api/student-profile', methods=['GET'])
def api_student_profile():
    email = request.args.get('email', '').strip()
    if not email:
        return jsonify({'found': False, 'reason': 'missing_email'}), 400

    user = User.query.filter(User.role == 'student', User.email.ilike(email)).first()
    if not user:
        return jsonify({'found': False, 'reason': 'not_found'})
    if user.status != 'approved':
        return jsonify({'found': False, 'reason': 'not_approved'})
    if user.profile_form_status != 'submitted' or not user.profile_form_data:
        return jsonify({'found': False, 'reason': 'not_submitted'})

    return jsonify({'found': True, 'student': serialize_student_profile_sync(user)})


@app.cli.command('init-db')
def init_db():
    """Create database tables."""
    ensure_user_schema()
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
