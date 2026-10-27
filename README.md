# AIRLINES member platform starter

A Flask/SQLite responsive website with registration/login, referral codes, a member dashboard, package request catalogue, team page, and deposit/withdrawal request records.

## Important
This is an original implementation inspired by common features of the referenced site, not a pixel-for-pixel copy. It intentionally does not include guaranteed daily returns, automatic commission payouts, fabricated payment confirmations, or automatic wallet crediting. Payment forms create pending records only; no money is moved.

## Run locally
```bash
pkg install python -y
pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python app.py
```
Open http://127.0.0.1:5000

## Render
Build command: `pip install -r requirements.txt`
Start command: `gunicorn app:app`
Set a long random `SECRET_KEY`. Set `DATABASE_PATH` to a persistent disk path if the deployment plan supports it. For production, add CSRF protection, rate limits, verified email/phone, audit logging, admin permissions, backups, and a compliant payment provider. SQLite on ephemeral storage can lose data during redeploys/restarts.
