# Complete Authentication / Gmail SMTP Setup

The portal includes:

- Student registration
- Student login/logout
- Secure password hashing
- Change password after login
- Forgot password
- One-time password-reset token
- 15-minute token expiry
- Reset link sent by Gmail SMTP
- Admin authentication

## 1. Configure `.env`

The project already contains a `.env` file. Replace the placeholder values:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=yourgmail@gmail.com
SMTP_PASSWORD=your_google_app_password
MAIL_FROM=yourgmail@gmail.com
SMTP_USE_TLS=1
```

Also replace:

```env
SECRET_KEY=replace-with-a-long-random-secret-key
ADMIN_PASSWORD=replace-with-a-strong-admin-password
```

## 2. Create a Gmail App Password

Do NOT put your normal Gmail password in `SMTP_PASSWORD`.

1. Sign in to the Gmail/Google account that will send reset emails.
2. Enable 2-Step Verification.
3. Open Google Account -> Security -> App passwords.
4. Create an app password for this project.
5. Put the generated 16-character app password in `SMTP_PASSWORD`.

Example:

```env
SMTP_USERNAME=myportal@gmail.com
SMTP_PASSWORD=abcdefghijklmnop
MAIL_FROM=myportal@gmail.com
```

## 3. Run the project

```bash
pip install -r requirements.txt
python app.py
```

Open the URL shown by Flask, then:

1. Register a student account with a real email address.
2. Log out.
3. Click `Forgot Password?`.
4. Enter the registered email.
5. Check the inbox/spam folder.
6. Open the reset link.
7. Set a new password.
8. Log in using the new password.

## 4. If email sending fails

Run Flask in debug mode temporarily:

```env
FLASK_DEBUG=1
```

The application logs the underlying SMTP exception. Common causes are:

- Wrong Gmail address
- Normal Gmail password used instead of App Password
- 2-Step Verification not enabled
- Incorrect SMTP port
- `.env` is not in the same directory as `app.py`
- Gmail account/security policy blocks the sign-in

After troubleshooting, set:

```env
FLASK_DEBUG=0
```

## 5. Important security rule

Never commit `.env` to GitHub. It is already included in `.gitignore`.

For deployment, configure these environment variables in the hosting provider instead of exposing them in source code.
