import os, sqlite3, secrets, re
from datetime import datetime, timezone
from functools import wraps
from decimal import Decimal, InvalidOperation
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort
from werkzeug.security import generate_password_hash, check_password_hash

ROOT=os.path.dirname(os.path.abspath(__file__))
DB=os.environ.get('DATABASE_PATH',os.path.join(ROOT,'airlines.db'))
ADMIN_PHONE=re.sub(r'\D','',os.environ.get('ADMIN_PHONE','0758878297'))
app=Flask(__name__)
app.secret_key=os.environ.get('SECRET_KEY','change-this-secret-before-deployment')
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax')

def now(): return datetime.now(timezone.utc).isoformat()
def norm_phone(s): return re.sub(r'\D','',s or '')
def db():
 c=sqlite3.connect(DB,timeout=20); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init_db():
 with db() as c:
  c.executescript("""
  CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE COLLATE NOCASE NOT NULL,email TEXT UNIQUE COLLATE NOCASE NOT NULL,phone TEXT NOT NULL DEFAULT '',password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'member',balance_cents INTEGER NOT NULL DEFAULT 0,referral_code TEXT UNIQUE NOT NULL,referred_by TEXT,created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS packages(id INTEGER PRIMARY KEY,name TEXT NOT NULL,price_cents INTEGER NOT NULL,daily_display_cents INTEGER NOT NULL DEFAULT 0,duration_days INTEGER NOT NULL DEFAULT 30,active INTEGER NOT NULL DEFAULT 1);
  CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id),package_id INTEGER NOT NULL REFERENCES packages(id),status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS payment_requests(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id),kind TEXT NOT NULL CHECK(kind IN ('deposit','withdrawal')),amount_cents INTEGER NOT NULL,network TEXT NOT NULL DEFAULT '',phone TEXT NOT NULL DEFAULT '',reference TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL,reviewed_at TEXT NOT NULL DEFAULT '',admin_note TEXT NOT NULL DEFAULT '');
  CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id),amount_cents INTEGER NOT NULL,entry_type TEXT NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL);
  """)
  # Safe additive migrations for earlier starter databases.
  cols={r['name'] for r in c.execute('PRAGMA table_info(users)').fetchall()}
  for name,decl in [('phone',"TEXT NOT NULL DEFAULT ''"),('role',"TEXT NOT NULL DEFAULT 'member'"),('balance_cents','INTEGER NOT NULL DEFAULT 0')]:
   if name not in cols: c.execute(f'ALTER TABLE users ADD COLUMN {name} {decl}')
  pcols={r['name'] for r in c.execute('PRAGMA table_info(payment_requests)').fetchall()}
  if 'reviewed_at' not in pcols: c.execute("ALTER TABLE payment_requests ADD COLUMN reviewed_at TEXT NOT NULL DEFAULT ''")
  if 'admin_note' not in pcols: c.execute("ALTER TABLE payment_requests ADD COLUMN admin_note TEXT NOT NULL DEFAULT ''")
  plans=[(1,'VIP 1',2000000,200000,30,1),(2,'VIP 2',10000000,1000000,30,1),(3,'VIP 3',50000000,5000000,30,1),(4,'VIP 4',100000000,10000000,30,1)]
  for p in plans: c.execute('INSERT INTO packages(id,name,price_cents,daily_display_cents,duration_days,active) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,price_cents=excluded.price_cents,daily_display_cents=excluded.daily_display_cents,duration_days=excluded.duration_days,active=excluded.active',p)

def find_user():
 if not session.get('user_id'): return None
 with db() as c: return c.execute('SELECT id,username,email,phone,role,balance_cents,referral_code,referred_by,created_at FROM users WHERE id=?',(session['user_id'],)).fetchone()
@app.before_request
def load_user(): g.user=find_user()
def login_required(fn):
 @wraps(fn)
 def w(*a,**kw):
  if not g.user: flash('Please sign in first.','error'); return redirect(url_for('login'))
  return fn(*a,**kw)
 return w
def admin_required(fn):
 @wraps(fn)
 @login_required
 def w(*a,**kw):
  if not g.user or g.user['role']!='admin': abort(403)
  return fn(*a,**kw)
 return w
def money(cents): return 'UGX {:,.0f}'.format((cents or 0)/100)
@app.context_processor
def helpers():
 return {'money':money,'payment_recipients':{'MTN':{'name':os.environ.get('AIRLINES_MTN_NAME','Mary Namara'),'number':os.environ.get('AIRLINES_MTN_NUMBER','0757837051')},'Airtel':{'name':os.environ.get('AIRLINES_AIRTEL_NAME','Mary Namara'),'number':os.environ.get('AIRLINES_AIRTEL_NUMBER','0757837051')}}}
@app.route('/')
def index(): return render_template('index.html')
@app.route('/register',methods=['GET','POST'])
def register():
 ref=request.args.get('ref','').strip()[:32]
 if request.method=='POST':
  username=request.form.get('username','').strip(); email=request.form.get('email','').strip().lower(); phone=request.form.get('phone','').strip(); password=request.form.get('password',''); ref=request.form.get('referral_code','').strip()[:32]
  if len(username)<3 or len(username)>30: flash('Username must be 3–30 characters.','error')
  elif '@' not in email: flash('Enter a valid email address.','error')
  elif len(norm_phone(phone))<9 or len(norm_phone(phone))>13: flash('Enter a valid phone number.','error')
  elif len(password)<8: flash('Password must be at least 8 characters.','error')
  else:
   code=secrets.token_hex(5).upper(); role='admin' if norm_phone(phone)==ADMIN_PHONE else 'member'
   try:
    with db() as c:
     valid=c.execute('SELECT referral_code FROM users WHERE referral_code=?',(ref,)).fetchone() if ref else None
     cur=c.execute('INSERT INTO users(username,email,phone,password_hash,role,balance_cents,referral_code,referred_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(username,email,phone,generate_password_hash(password),role,800000,code,valid['referral_code'] if valid else None,now()))
     c.execute('INSERT INTO ledger(user_id,amount_cents,entry_type,note,created_at) VALUES(?,?,?,?,?)',(cur.lastrowid,800000,'welcome_bonus','UGX 8,000 welcome bonus; promotional credit, subject to platform terms',now()))
     session['user_id']=cur.lastrowid
    flash('Account created. UGX 8,000 welcome bonus recorded.','success')
    if role=='admin': flash('Administrator access enabled for this account. Ensure this phone number is verified before public launch.','info')
    return redirect(url_for('admin') if role=='admin' else url_for('dashboard'))
   except sqlite3.IntegrityError: flash('That username or email is already registered.','error')
 return render_template('register.html',ref=ref)
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  ident=request.form.get('identity','').strip()
  with db() as c: u=c.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE OR email=? COLLATE NOCASE OR phone=?',(ident,ident,ident)).fetchone()
  if u and check_password_hash(u['password_hash'],request.form.get('password','')):
   session.clear(); session['user_id']=u['id']; return redirect(url_for('admin') if u['role']=='admin' else url_for('dashboard'))
  flash('Incorrect login details.','error')
 return render_template('login.html')
@app.post('/logout')
def logout(): session.clear(); return redirect(url_for('index'))
@app.route('/dashboard')
@login_required
def dashboard():
 with db() as c:
  orders=c.execute('SELECT o.*,p.name,p.price_cents,p.duration_days FROM orders o JOIN packages p ON p.id=o.package_id WHERE o.user_id=? ORDER BY o.id DESC',(g.user['id'],)).fetchall()
  payments=c.execute('SELECT * FROM payment_requests WHERE user_id=? ORDER BY id DESC LIMIT 8',(g.user['id'],)).fetchall()
  directs=c.execute('SELECT COUNT(*) n FROM users WHERE referred_by=?',(g.user['referral_code'],)).fetchone()['n']
  ledger=c.execute('SELECT * FROM ledger WHERE user_id=? ORDER BY id DESC LIMIT 10',(g.user['id'],)).fetchall()
 return render_template('dashboard.html',orders=orders,payments=payments,directs=directs,ledger=ledger)
@app.route('/packages')
@login_required
def packages():
 with db() as c: rows=c.execute('SELECT * FROM packages WHERE active=1 ORDER BY id').fetchall()
 return render_template('packages.html',packages=rows)
@app.post('/package/<int:pid>/order')
@login_required
def order_package(pid):
 with db() as c:
  p=c.execute('SELECT * FROM packages WHERE id=? AND active=1',(pid,)).fetchone()
  if not p: flash('Package not found.','error')
  else:
   cur=c.execute('INSERT INTO orders(user_id,package_id,status,created_at) VALUES(?,?,?,?)',(g.user['id'],pid,'pending',now()))
   flash(f'Package request #{cur.lastrowid} submitted for review.','success')
 return redirect(url_for('dashboard'))
@app.route('/payments',methods=['GET','POST'])
@login_required
def payments():
 if request.method=='POST':
  kind=request.form.get('kind',''); network=request.form.get('network',''); phone=request.form.get('phone','').strip()[:40]; ref=request.form.get('reference','').strip()[:100]
  try:
   amount=Decimal(request.form.get('amount','0')); cents=int(amount*100)
   if amount<=0 or amount*100!=(amount*100).to_integral_value(): raise InvalidOperation
  except (InvalidOperation,ValueError): flash('Enter a valid positive UGX amount.','error'); return redirect(url_for('payments'))
  if kind not in ('deposit','withdrawal'): flash('Choose a valid request type.','error')
  elif kind=='deposit' and cents<2000000: flash('Minimum deposit is UGX 20,000.','error')
  elif kind=='withdrawal' and cents<1000000: flash('Minimum withdrawal is UGX 10,000.','error')
  elif not phone: flash('Enter your mobile-money phone number.','error')
  elif kind=='withdrawal' and datetime.now().weekday()>=5: flash('Withdrawals are accepted Monday to Friday only.','error')
  elif kind=='withdrawal' and cents>g.user['balance_cents']: flash('Requested amount exceeds your available balance.','error')
  else:
   with db() as c: c.execute('INSERT INTO payment_requests(user_id,kind,amount_cents,network,phone,reference,status,created_at) VALUES(?,?,?,?,?,?,?,?)',(g.user['id'],kind,cents,network,phone,ref,'pending',now()))
   flash('Request submitted for administrator review. Deposits are credited only after manual verification.','success'); return redirect(url_for('dashboard'))
 return render_template('payments.html')
@app.route('/team')
@login_required
def team():
 with db() as c:
  directs=c.execute('SELECT username,created_at,referral_code FROM users WHERE referred_by=? ORDER BY id DESC',(g.user['referral_code'],)).fetchall()
  # Show L1/L2/L3 network counts; commissions are informational only and not credited automatically.
  l2=c.execute('SELECT COUNT(*) n FROM users u JOIN users d ON u.referred_by=d.referral_code WHERE d.referred_by=?',(g.user['referral_code'],)).fetchone()['n']
  l3=c.execute('SELECT COUNT(*) n FROM users u JOIN users d ON u.referred_by=d.referral_code JOIN users e ON d.referred_by=e.referral_code WHERE e.referred_by=?',(g.user['referral_code'],)).fetchone()['n']
 return render_template('team.html',directs=directs,l2=l2,l3=l3)
@app.route('/admin')
@admin_required
def admin():
 with db() as c:
  pending=c.execute("SELECT p.*,u.username,u.phone AS user_phone FROM payment_requests p JOIN users u ON u.id=p.user_id WHERE p.status='pending' ORDER BY p.id").fetchall()
  users=c.execute('SELECT id,username,email,phone,role,balance_cents,created_at FROM users ORDER BY id DESC LIMIT 100').fetchall()
  packages=c.execute('SELECT * FROM packages ORDER BY id').fetchall()
  totals=c.execute('SELECT COUNT(*) n FROM users').fetchone()['n']
 return render_template('admin.html',pending=pending,users=users,packages=packages,total_users=totals)
@app.post('/admin/payment/<int:rid>/<action>')
@admin_required
def review_payment(rid,action):
 if action not in ('approve','reject'): abort(404)
 note=request.form.get('note','').strip()[:200]
 with db() as c:
  p=c.execute('SELECT * FROM payment_requests WHERE id=?',(rid,)).fetchone()
  if not p or p['status']!='pending': flash('Request not found or already reviewed.','error')
  elif action=='approve' and p['kind']=='withdrawal' and p['amount_cents']>c.execute('SELECT balance_cents FROM users WHERE id=?',(p['user_id'],)).fetchone()['balance_cents']:
   flash('Cannot approve withdrawal: insufficient available balance.','error')
  else:
   status='approved' if action=='approve' else 'rejected'
   c.execute('UPDATE payment_requests SET status=?,reviewed_at=?,admin_note=? WHERE id=?',(status,now(),note,rid))
   if action=='approve' and p['kind']=='deposit':
    c.execute('UPDATE users SET balance_cents=balance_cents+? WHERE id=?',(p['amount_cents'],p['user_id']))
    c.execute('INSERT INTO ledger(user_id,amount_cents,entry_type,note,created_at) VALUES(?,?,?,?,?)',(p['user_id'],p['amount_cents'],'deposit','Admin-approved deposit request #'+str(rid),now()))
   elif action=='approve' and p['kind']=='withdrawal':
    # Apply 20% displayed withholding; deduct full request and credit payout net in ledger for transparency.
    tax=p['amount_cents']//5; net=p['amount_cents']-tax
    c.execute('UPDATE users SET balance_cents=balance_cents-? WHERE id=?',(p['amount_cents'],p['user_id']))
    c.execute('INSERT INTO ledger(user_id,amount_cents,entry_type,note,created_at) VALUES(?,?,?,?,?)',(p['user_id'],-p['amount_cents'],'withdrawal','Approved withdrawal #'+str(rid)+'. Requested amount; estimated 20% withholding UGX '+format(tax/100,',.0f')+'; net UGX '+format(net/100,',.0f'),now()))
   flash('Payment request '+status+'. Balance updated only after admin approval where applicable.','success')
 return redirect(url_for('admin'))
@app.post('/admin/package/<int:pid>/toggle')
@admin_required
def toggle_package(pid):
 with db() as c: c.execute('UPDATE packages SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(pid,))
 flash('Package status updated.','success'); return redirect(url_for('admin'))
@app.route('/health')
def health(): return {'status':'ok'}
@app.errorhandler(403)
def forbidden(_): return render_template('error.html',code=403,message='Administrator access required.'),403
@app.errorhandler(404)
def missing(_): return render_template('error.html',code=404,message='Page not found.'),404
init_db()
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')),debug=False)
