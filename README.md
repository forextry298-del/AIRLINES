# AIRLINES

Flask + SQLite member portal for local testing. Includes registration/login, UGX balances, UGX 8,000 welcome ledger credit, VIP catalogue, referral level counts, MTN/Airtel deposit recipient display, pending deposit/withdrawal requests, and an admin review panel.

## Run locally

```bash
pip install -r requirements.txt
export SECRET_KEY="replace-with-a-long-random-secret"
export ADMIN_PHONE="0758878297"
python app.py
```

Open http://127.0.0.1:5000. The account registered with the configured `ADMIN_PHONE` receives the admin role. **This starter does not verify phone ownership via OTP. Do not expose it publicly until you add verified admin provisioning, CSRF protection, rate limiting, HTTPS, secure secrets, backups, and a proper audit/security review.**

## Recipient configuration

Defaults for MTN and Airtel: Mary Namara, `0757837051`. For deployment, configure `AIRLINES_MTN_NAME`, `AIRLINES_MTN_NUMBER`, `AIRLINES_AIRTEL_NAME`, and `AIRLINES_AIRTEL_NUMBER` as environment variables.

## Important financial limitations

Payments are not integrated with MTN/Airtel APIs. Admin approval is manual and should only happen after independently verifying receipt. Package daily figures are illustrative only; there are no automatic daily rewards or referral commission payouts. Withdrawal requests are records, not actual transfers. The reference's 20% withdrawal tax must be legally verified before use. Do not use the starter to misrepresent guaranteed returns.
