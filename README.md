# AIRLINES platform — v5

Flask/SQLite member portal with registration, referral tracking, package requests, payment requests, admin review, machine illustrations, a daily countdown, and scheduled credits constrained by a separately funded earnings reserve.

## Local run

```bash
pip install -r requirements.txt
export SECRET_KEY="replace-with-a-long-random-secret"
export ADMIN_PHONE="0758878297"
python app.py
```

## Render

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Set a strong `SECRET_KEY` and `ADMIN_PHONE` environment variables.
- Configure durable storage for the database (or migrate to a managed PostgreSQL database) before accepting real customer balances.

## Scheduled daily credits

A machine request stays pending until an administrator approves it. Approval deducts the machine price from the user's available balance and starts the 24-hour timer. The scheduler checks due orders approximately once per minute while the web service is running. A credit is issued only when the separate `earnings_reserve` has sufficient funds; the reserve is reduced in the same database transaction, and a unique `(order_id, credit_day)` constraint prevents duplicate credits. If the reserve is insufficient, credits pause until verified funds are recorded by an administrator. Configure only funds genuinely available from lawful business revenue; customer deposits must not be represented as profit or used to promise guaranteed returns.

Admin reserve funding is a manual accounting record, not a bank or mobile-money verification. Verify the source independently before adding reserve funds.

## Payment limitations and production safety

- MTN/Airtel details are display-only. This app does not connect to an official Mobile Money API, automatically verify transaction IDs, or send real payouts.
- Admin approval must only happen after independent payment verification.
- Phone-number matching alone is not strong admin authentication; verify ownership and add MFA/OTP before public launch.
- This starter needs CSRF protection, rate limiting, secure admin onboarding, database backups, monitoring, and a production review before handling real money.
- The package SVGs in `static/products/` are original AIRLINES illustrations, not copied source-site assets. Exact third-party product images were not exposed by the page text extraction, so these original images are used instead.

## Referral links

Registration accepts `?ref=REFERRAL_CODE`. Referral counts are tracked; this version does not automatically pay referral commissions.
