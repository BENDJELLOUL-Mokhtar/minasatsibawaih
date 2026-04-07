from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
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
    return render_template('admin.html', users=users)


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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
