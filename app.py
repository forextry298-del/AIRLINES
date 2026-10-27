import os, sqlite3
from datetime import datetime, timezone
from functools import wraps
from decimal import Decimal, InvalidOperation
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("DATABASE_PATH", os.path.join(ROOT, "airlines.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-deployment")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

def db():
    con = sqlite3.connect(DB, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE COLLATE NOCASE NOT NULL,
          email TEXT UNIQUE COLLATE NOCASE NOT NULL, password_hash TEXT NOT NULL,
          referral_code TEXT UNIQUE NOT NULL, referred_by TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS packages(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, price_cents INTEGER NOT NULL,
          daily_display_cents INTEGER NOT NULL DEFAULT 0, duration_days INTEGER NOT NULL DEFAULT 30,
          active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS orders(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
          package_id INTEGER NOT NULL REFERENCES packages(id), status TEXT NOT NULL DEFAULT 'pending',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS payment_requests(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
          kind TEXT NOT NULL CHECK(kind IN ('deposit','withdrawal')), amount_cents INTEGER NOT NULL,
          network TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', reference TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gift_ledger(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
          entry_type TEXT NOT NULL, amount_cents INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL
        );
        """)
        defaults = [
          (1,"Airlines Starter",2000,0,30,1),
          (2,"Airlines Plus",10000,0,60,1),
          (3,"Airlines Premium",50000,0,90,1),
        ]
        for row in defaults:
            c.execute("INSERT OR IGNORE INTO packages(id,name,price_cents,daily_display_cents,duration_days,active) VALUES(?,?,?,?,?,?)", row)

def find_user():
    if not session.get("user_id"): return None
    with db() as c:
        return c.execute("SELECT id,username,email,referral_code,referred_by,created_at FROM users WHERE id=?", (session["user_id"],)).fetchone()

@app.before_request
def load_user():
    g.user = find_user()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.user:
            flash("Please sign in to continue.", "info")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def money(cents): return f"${cents / 100:,.2f}"

@app.context_processor
def inject_helpers():
    return {"money": money}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    ref = request.args.get("ref","").strip()[:32]
    if request.method == "POST":
        username=request.form.get("username","").strip()
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        ref=request.form.get("referral_code","").strip()[:32]
        if len(username)<3 or len(username)>30: flash("Username must be 3–30 characters.","error")
        elif "@" not in email: flash("Enter a valid email address.","error")
        elif len(password)<8: flash("Password must be at least 8 characters.","error")
        else:
            code=os.urandom(5).hex().upper()
            try:
                with db() as c:
                    valid_ref = c.execute("SELECT referral_code FROM users WHERE referral_code=?", (ref,)).fetchone() if ref else None
                    cur=c.execute("INSERT INTO users(username,email,password_hash,referral_code,referred_by,created_at) VALUES(?,?,?,?,?,?)",
                      (username,email,generate_password_hash(password),code,valid_ref["referral_code"] if valid_ref else None,datetime.now(timezone.utc).isoformat()))
                    session["user_id"]=cur.lastrowid
                flash("Account created successfully.","success")
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("That username or email is already registered.","error")
    return render_template("register.html", ref=ref)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        ident=request.form.get("identity","").strip()
        with db() as c: u=c.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE OR email=? COLLATE NOCASE",(ident,ident)).fetchone()
        if u and check_password_hash(u["password_hash"],request.form.get("password","")):
            session.clear(); session["user_id"]=u["id"]
            return redirect(url_for("dashboard"))
        flash("Incorrect login details.","error")
    return render_template("login.html")

@app.post("/logout")
def logout():
    session.clear(); return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as c:
        orders=c.execute("SELECT o.*,p.name,p.price_cents,p.duration_days FROM orders o JOIN packages p ON p.id=o.package_id WHERE o.user_id=? ORDER BY o.id DESC",(g.user["id"],)).fetchall()
        payments=c.execute("SELECT * FROM payment_requests WHERE user_id=? ORDER BY id DESC LIMIT 8",(g.user["id"],)).fetchall()
        sent=c.execute("SELECT COALESCE(SUM(amount_cents),0) n FROM payment_requests WHERE user_id=? AND kind='deposit' AND status='approved'",(g.user["id"],)).fetchone()["n"]
        directs=c.execute("SELECT COUNT(*) n FROM users WHERE referred_by=?",(g.user["referral_code"],)).fetchone()["n"]
    return render_template("dashboard.html",orders=orders,payments=payments,approved_deposits=sent,directs=directs)

@app.route("/packages")
@login_required
def packages():
    with db() as c: rows=c.execute("SELECT * FROM packages WHERE active=1 ORDER BY id").fetchall()
    return render_template("packages.html",packages=rows)

@app.post("/package/<int:pid>/order")
@login_required
def order_package(pid):
    with db() as c:
        p=c.execute("SELECT * FROM packages WHERE id=? AND active=1",(pid,)).fetchone()
        if not p: flash("Package not found.","error")
        else:
            cur=c.execute("INSERT INTO orders(user_id,package_id,status,created_at) VALUES(?,?,?,?)",
                (g.user["id"],pid,"pending",datetime.now(timezone.utc).isoformat()))
            flash(f"Order #{cur.lastrowid} created as pending. It is not a payment or investment confirmation.","success")
    return redirect(url_for("dashboard"))

@app.route("/payments", methods=["GET","POST"])
@login_required
def payments():
    if request.method=="POST":
        kind=request.form.get("kind","")
        network=request.form.get("network","")
        phone=request.form.get("phone","").strip()[:40]
        ref=request.form.get("reference","").strip()[:100]
        try:
            amount=Decimal(request.form.get("amount","0"))
            cents=int(amount*100)
            if amount<=0 or amount*100 != (amount*100).to_integral_value(): raise InvalidOperation
        except (InvalidOperation,ValueError):
            flash("Enter a valid positive USD amount with up to two decimal places.","error")
            return redirect(url_for("payments"))
        if kind not in ("deposit","withdrawal"): flash("Choose a valid request type.","error")
        elif not phone: flash("Enter the payment phone/account details.","error")
        elif kind=="withdrawal" and cents<1000: flash("Minimum withdrawal request is $10.00.","error")
        else:
            with db() as c:
                c.execute("INSERT INTO payment_requests(user_id,kind,amount_cents,network,phone,reference,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
                  (g.user["id"],kind,cents,network,phone,ref,"pending",datetime.now(timezone.utc).isoformat()))
            flash("Request submitted for manual review. No money was moved or credited by this form.","success")
            return redirect(url_for("dashboard"))
    return render_template("payments.html")

@app.route("/team")
@login_required
def team():
    with db() as c:
        directs=c.execute("SELECT username,created_at FROM users WHERE referred_by=? ORDER BY id DESC",(g.user["referral_code"],)).fetchall()
        counts=[]
        for u in directs:
            counts.append(u)
    return render_template("team.html",directs=directs)

@app.route("/health")
def health(): return {"status":"ok"}

@app.errorhandler(404)
def missing(_): return render_template("error.html",code=404,message="Page not found."),404

init_db()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","5000")),debug=False)
