# হোস্টিং গাইড — PythonAnywhere (ফ্রি)

এই অ্যাপটি **Flask + SQLite**। Static হোস্টিং (GitHub Pages / Netlify / Vercel) এ চলবে না, কারণ ওখানে Python রান করে না এবং SQLite ফাইলে লেখা যায় না। **PythonAnywhere** এর ফ্রি টিয়ারে ডিস্ক পার্মানেন্ট, তাই `records.db`-এর জব লগ টিকে থাকে — এটাই এই প্রজেক্টের জন্য সবচেয়ে উপযুক্ত ফ্রি অপশন।

---

## ১. কোন ফাইল কী কাজ করে

| ফাইল | কাজ |
| --- | --- |
| [app.py](./app.py) | মূল অ্যাপ। এখন ডেটাবেসের পাথ `__file__` থেকে অ্যাবসোলিউট হয়, তাই যে ডিরেক্টরি থেকেই WSGI চালানো হোক কাজ করবে। |
| `wsgi.py` | প্রোডাকশন এন্ট্রি পয়েন্ট। PythonAnywhere/gunicorn এটাই ইমপোর্ট করে। |
| [requirements.txt](./requirements.txt) | `pip install -r requirements.txt` দিয়ে ইনস্টল। |
| `templates/*.html` | UI (Tailwind + Leaflet CDN থেকে লোড হয়, সব HTTPS)। |
| `records.db` | অ্যাপের ডেটা। **git-এ যায় না** (`.gitignore`-এ আছে)। |

---

## ২. ধাপে ধাপে PythonAnywhere

### ধাপ ১ — অ্যাকাউন্ট
[pythonanywhere.com](https://www.pythonanywhere.com) → **Pricing & signup** → **Create a Beginner account** (ফ্রি, কার্ড লাগে না)।
আপনার সাবডোমেইন হবে: `https://<username>.pythonanywhere.com`

### ধাপ ২ — কোড আপলোড (দুইটি উপায়)

**উপায় ক — GitHub দিয়ে (রেকমেন্ডেড)**

রিপো: `https://github.com/s4elim/Fiber-and-user-location-manage` (branch `main`, **পাবলিক**)। রিমোট আগেই কনফিগার করা, তাই লোকাল থেকে শুধু পুশ করুন:
```bash
git push origin main
```
> `.gitignore` থাকায় `records.db` / `instance/` / `.env` পুশ হয় না — পাবলিক রিপোতেও কোনো গোপন তথ্য (পাসওয়ার্ড হ্যাশ, সেশন কী) যায় না।

তারপর PythonAnywhere-এ **Consoles → Bash** খুলে (প্রথমবার এক কমান্ডে সব):
```bash
cd ~
git clone https://github.com/s4elim/Fiber-and-user-location-manage.git technician_app
cd technician_app
mkvirtualenv --python=/usr/bin/python3.10 venv
pip install -r requirements.txt
python -c "import app; print('DB:', app.DB_NAME)"
```
শেষ লাইনে `/home/<username>/technician_app/records.db` প্রিন্ট হলে ধাপ ৩–৬ এমনিতেই শেষ — সরাসরি Web ট্যাবে যান। পাবলিক রিপো হওয়ায় কোনো GitHub টোকেন লাগবে না।

**উপায় খ — ফাইল আপলোড (Git চাই না)**

লোকাল মেশিনে `technician_app` ফোল্ডারের zip বানিয়ে PythonAnywhere-এর **Files** ট্যাবে গিয়ে আপলোড করুন, তারপর Bash-এ:
```bash
cd ~
unzip technician_app.zip -d technician_app
```

### ধাপ ৩ — virtualenv ও প্যাকেজ

Bash কনসোলে:
```bash
cd ~/technician_app
mkvirtualenv --python=/usr/bin/python3.10 venv
pip install -r requirements.txt
python -c "import app; print('DB:', app.DB_NAME)"
```
শেষ লাইনে প্রিন্ট হওয়া উচিত: `/home/<username>/technician_app/records.db`

### ধাপ ৪ — Web app তৈরি

**Web** ট্যাব → **Add a new web app** → **Next** (ডিফল্ট ডোমেইনটাই রাখুন) → **Manual configuration** (Flask টেমপ্লেট নয়) → **Python 3.10** → **Next**।

> ⚠️ Web অ্যাপে যে Python ভার্সন বাছবেন, virtualenv-এ **ঠিক সেই ভার্সনই** দিতে হবে (৩.১০ বাছলে `--python=/usr/bin/python3.10`, ৩.১৩ হলে `python3.13`)। মিল না হলে সার্ভার চালু হবে না। ফ্রি টিয়ারে ভার্সন বদলাতে "Web" ট্যাব থেকেই নতুন করে বাছতে হয়।

তারপর ওই পেজেই:
- **Source code**: `/home/<username>/technician_app`
- **Working directory**: `/home/<username>/technician_app`
- **Virtualenv**: `/home/<username>/.virtualenvs/venv`

### ধাপ ৫ — WSGI ফাইল সেট করা

Web ট্যাবে **WSGI configuration file** লিংকে ক্লিক করুন (পাথ: `/var/www/<username>_pythonanywhere_com_wsgi.py`)। ভেতরের সব মুছে দিয়ে এটুকু বসান:

```python
import sys

project_path = "/home/<username>/technician_app"
if project_path not in sys.path:
    sys.path.insert(0, project_path)

from wsgi import application
```

> `wsgi.py` নিজেই প্রজেক্ট ডিরেক্টরি sys.path-এ যোগ করে, তাই এই ৪ লাইনই যথেষ্ট। `from app import app as application`-ও কাজ করবে, কিন্তু `from wsgi import application` সবচেয়ে নিরাপদ।

### ধাপ ৬ — Environment variables (সবচেয়ে গুরুত্বপূর্ণ ধাপ)

Web ট্যাবের নিচে **Environment variables** সেকশনে **Add a new variable** দিয়ে যোগ করুন:

| Variable | মান | কেন দরকার |
| --- | --- | --- |
| `FLASK_SECRET_KEY` | লম্বা র‍্যান্ডম স্ট্রিং (যেমন `python -c "import secrets;print(secrets.token_hex(32))"`) | এটা না দিলে প্রতিবার রিলোডে সেশন কী বদলে যায় → সব ইউজার লগআউট হয়ে পড়ে। |
| `ADMIN_USERNAME` | আপনার মেইন অ্যাডমিন ইউজারনেম | প্রথমবার ডেটাবেস খালি থাকলে এই অ্যাকাউন্টটাই তৈরি হবে। |
| `ADMIN_PASSWORD` | ৮+ ক্যারেক্টারের পাসওয়ার্ড | মেইন অ্যাডমিনের প্রথম পাসওয়ার্ড। |
| `APP_TIMEZONE` | `Asia/Dhaka` | সার্ভার UTC-তে চলে; এটা না দিলে জব লগের সময় ৬ ঘণ্টা পিছিয়ে দেখাবে। |
| `SESSION_COOKIE_SECURE` | `1` | HTTPS-এ কুকি সুরক্ষিত রাখে (PythonAnywhere ডিফল্টেই HTTPS)। |

### ধাপ ৭ — ডেটাবেস

নতুন করে শুরু করলে কিছু করার নেই — প্রথম রিকোয়েস্টেই `records.db` ও টেবিল তৈরি হবে (এবং `ADMIN_USERNAME`/`ADMIN_PASSWORD` থেকে মেইন অ্যাডমিন)।

পুরনো ডেটা নিয়ে যেতে চাইলে লোকাল `records.db` ফাইলটা **Files** ট্যাব দিয়ে `/home/<username>/technician_app/` এ আপলোড করুন (অথবা লোকাল মেশিন থেকে `scp records.db <username>@ssh.pythonanywhere.com:~/technician_app/`)।

> ⚠️ `records.db`-তে পাসওয়ার্ড হ্যাশ ও কাস্টমারের তথ্য আছে। পাবলিক GitHub-এ বা কারও সাথে শেয়ার করবেন না। নিয়মিত ব্যাকআপ নিন:
> ```bash
> cp ~/technician_app/records.db ~/records-backup-$(date +%F).db
> ```

### ধাপ ৮ — Reload ও টেস্ট

উপরে **Reload** বাটনে ক্লিক করুন (কোড বদলালেই ক্লিক করতে হবে), তারপর চেক করুন:

- `https://<username>.pythonanywhere.com/` → টেকনিশিয়ান ফর্ম ওপেন হয়
- `/admin/login` → মেইন অ্যাডমিন দিয়ে লগইন হয়
- ফর্ম থেকে একটা টেস্ট জব সেভ হয় → `/admin`-এ দেখা যায়
- মোবাইলে GPS লোকেশন আসে (HTTPS থাকায় ব্রাউজার লোকেশন পারমিশন দেবে)

### পরে কোড বদলালে (আপডেট দেওয়ার নিয়ম)

```bash
# ১) লোকাল মেশিনে
git push origin main

# ২) PythonAnywhere Bash-এ
cd ~/technician_app && git pull

# ৩) Web ট্যাবে "Reload" ক্লিক
```
শুধু টেমপ্লেট/HTML বদলালেও Reload লাগবে। ভেরিয়েবল বদলালে সেটিংস সেভ করে আবার Reload দিন।

### ফ্রি টিয়ারের সীমা (জেনে রাখুন)

- **প্রতি ৩ মাসে একবার** Web ট্যাবে "Run until 3 months from today" বাটনে ক্লিক করতে হবে, নাহলে সাইট বন্ধ হয়ে যাবে (মেইলে রিমাইন্ডার আসে)।
- দিনে ~১০০ CPU সেকেন্ড — এই অ্যাপের লোডে যথেষ্ট।
- ফ্রি টিয়ারে **কাস্টম ডোমেইন নেই**; `<username>.pythonanywhere.com` সাবডোমেইনই পাবেন।
- আউটবাউন্ড ইন্টারনেট শুধু হোয়াইটলিস্টেড সাইটে (আপনার অ্যাপ বাইরের কোনো API কল করে না, তাই সমস্যা নেই)।

---

## ৩. লোকাল ডেভেলপমেন্ট (আগের মতোই)

```bash
pip install -r requirements.txt
set FLASK_SECRET_KEY=dev-key-change-me
python app.py
```
তারপর `http://127.0.0.1:5000`। মোবাইল থেকে টেস্ট করতে চাইলে একই Wi-Fi-তে থেকে `http://<আপনার-PC-এর-IP>:5000` খুলুন — ডিফল্ট হোস্ট এখন `0.0.0.0`, তাই LAN IP বদলালেও কোড এডিট করতে হবে না। পোর্ট বদলাতে `set FLASK_PORT=8000`।

---

## ৪. সমস্যা ও সমাধান

| সমস্যা | কারণ ও সমাধান |
| --- | --- |
| **Unhandled exception / 500** | Web ট্যাবের **Error log** দেখুন। সাধারণত `pip install` হয়নি বা WSGI ফাইলে পাথ ভুল। |
| **প্রতিবার লগআউট হয়ে যায়** | `FLASK_SECRET_KEY` সেট করা নেই। ধাপ ৬ দেখুন। |
| **`/admin/login`-এ "No admin account is configured"** | `ADMIN_USERNAME`/`ADMIN_PASSWORD` সেট করার **আগে** ডেটাবেস তৈরি হয়ে গেছে। সমাধান: ভেরিয়েবল দুটো যোগ করে Reload দিন, অথবা `~/technician_app/records.db` ডিলিট করে আবার Reload দিন (পুরনো ডেটা থাকলে ডিলিট করবেন না — বদলে Bash-এ `python -c "import app; app.init_db()"`)। |
| **`sqlite3.OperationalError: database is locked`** | একই ফাইলে একসাথে অনেক write। PythonAnywhere-এ একটাই প্রসেস চলে, তাই সাধারণত হয় না; gunicorn-এ গেলে `--workers 1` রাখুন। |
| **সময় ৬ ঘণ্টা পিছনে** | `APP_TIMEZONE=Asia/Dhaka` যোগ করে Reload দিন। |
| **CSS/ম্যাপ দেখা যাচ্ছে না** | Tailwind ও Leaflet CDN থেকে আসে; ইন্টারনেট/অ্যাডব্লক চেক করুন। অ্যাপের সার্ভার সাইডে কিছু করার নেই। |
| **পুরনো ডেটা হারিয়ে গেছে** | `records.db` আপলোড করা হয়নি, অথবা নতুন করে তৈরি হয়েছে। Bash-এ `ls -l ~/technician_app/records.db` দিয়ে দেখুন। |

---

## ৫. পরে চাইলে (ঐচ্ছিক হার্ডেনিং)

- **SQLite lock নিরাপদ করতে**: সব `sqlite3.connect(DB_NAME)` কে `sqlite3.connect(DB_NAME, timeout=15)` বানানো + `PRAGMA journal_mode=WAL` — একাধিক ইউজার একসাথে সেভ করলে উপকারে আসে।
- **CSRF/session আরও শক্ত করতে**: `SESSION_COOKIE_SECURE=1` সবসময় চালু রাখা (HTTPS আছে যেহেতু)।
- **অটো ব্যাকআপ**: PythonAnywhere-এ "Tasks" (ফ্রি টিয়ারে দিনে ১টা) দিয়ে প্রতিদিন `records.db` কপি।
- **কাস্টম ডোমেইন** চাইলে: Cloudflare-এ ডোমেইন কিনে PythonAnywhere-এর পেইড টিয়ার, অথবা ফ্রি রাখতে চাইলে নিজের PC + Cloudflare Tunnel।
