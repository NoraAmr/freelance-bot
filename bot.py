import os
import json
import time
import hashlib
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ─── CONFIG ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "***REDACTED***")
CHAT_ID          = os.environ.get("CHAT_ID", "***REDACTED***")
MOSTAQL_EMAIL    = os.environ.get("MOSTAQL_EMAIL", "***REDACTED***")       # DM monitoring — needs mostaql.com login, not Gmail
MOSTAQL_PASSWORD = os.environ.get("MOSTAQL_PASSWORD", "***REDACTED***")    # DM monitoring — needs mostaql.com login, not Gmail
CHECK_INTERVAL   = int(os.environ.get("CHECK_INTERVAL", "1800"))
SEEN_FILE        = "seen_jobs.json"
SEEN_DMS_FILE    = "seen_dms.json"
# ───────────────────────────────────────────────────────────────────────────────

KEYWORDS = {
    "🧠 AI & Software": [
        "ذكاء اصطناعي", "ai", "machine learning", "تعلم آلي", "deep learning",
        "chatgpt", "llm", "nlp", "python", "بايثون", "data science",
        "تطوير برمجي", "software", "برمجة", "تطبيق", "mobile", "موبايل",
        "android", "ios", "flutter", "react native", "تطبيق جوال",
    ],
    "🌐 Websites & Web Dev": [
        "موقع", "website", "web", "wordpress", "ووردبريس", "shopify",
        "متجر إلكتروني", "تصميم موقع", "frontend", "backend", "fullstack",
        "html", "css", "javascript", "react", "vue", "laravel", "django",
        "php", "سيو", "seo", "landing page", "صفحة هبوط",
    ],
    "📱 Telegram Bots": [
        "بوت تيليجرام", "telegram bot", "تيليجرام بوت", "بوت",
        "bot telegram", "برمجة بوت", "تطوير بوت", "telegram",
        "تيليغرام", "بوتات", "aiogram", "python telegram",
    ],
    "🎨 Graphic Design & UI/UX": [
        "تصميم", "design", "شعار", "logo", "هوية", "brand",
        "ui", "ux", "واجهة", "figma", "photoshop", "illustrator",
        "موشن", "motion", "فيديو موشن", "انفوجرافيك", "infographic",
        "بنر", "banner", "تصميم جرافيك", "graphic", "بروفايل",
        "سوشيال ميديا", "social media design", "منشور", "post design",
    ],
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.9",
}

PLATFORMS = {
    "mostaql":  "🟢 مستقل",
    "khamsat":  "🟣 خمسات",
    "kafeel":   "🔵 كفيل",
    "nafzly":   "🟠 نافذة",
}

# ─── PERSISTENCE ───────────────────────────────────────────────────────────────

def load_json(path: str) -> set:
    if os.path.exists(path):
        with open(path, "r") as f:
            return set(json.load(f))
    return set()


def save_json(path: str, data: set):
    with open(path, "w") as f:
        json.dump(list(data), f)

# ─── TELEGRAM ──────────────────────────────────────────────────────────────────

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        logger.info("✅ Telegram message sent.")
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")

# ─── KEYWORD MATCHING ──────────────────────────────────────────────────────────

def get_matching_category(title: str, desc: str) -> str | None:
    combined = (title + " " + desc).lower()
    for category, words in KEYWORDS.items():
        if any(w.lower() in combined for w in words):
            return category
    return None

# ─── SCRAPERS ──────────────────────────────────────────────────────────────────

def scrape_mostaql() -> list[dict]:
    jobs = []
    urls = [
        "https://mostaql.com/projects?sort=latest",
        "https://mostaql.com/projects?category=programming&sort=latest",
        "https://mostaql.com/projects?category=design&sort=latest",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            rows = soup.select("tr.project-row") or soup.select("table.projects-table tbody tr")
            for row in rows:
                title_el = row.select_one("h2.project__title a, h2 a, .project-title a")
                if not title_el:
                    continue
                title  = title_el.get_text(strip=True)
                link   = title_el.get("href", "")
                if link and not link.startswith("http"):
                    link = "https://mostaql.com" + link
                desc_el   = row.select_one(".project__brief, .project-brief, p.brief")
                desc      = desc_el.get_text(strip=True) if desc_el else ""
                budget_el = row.select_one(".project-price, .budget, .price")
                budget    = budget_el.get_text(strip=True) if budget_el else "غير محدد"
                jid       = hashlib.md5(link.encode()).hexdigest()
                jobs.append({"id": jid, "title": title, "desc": desc, "link": link, "budget": budget, "platform": "mostaql"})
        except Exception as e:
            logger.error(f"[mostaql] scrape error: {e}")
    return jobs


def scrape_khamsat() -> list[dict]:
    """
    خمسات — services marketplace (sellers offer services, not projects).
    We monitor the 'requests' section where buyers post what they need.
    """
    jobs = []
    urls = [
        "https://khamsat.com/community/requests?sort=latest",
        "https://khamsat.com/community/requests/programming?sort=latest",
        "https://khamsat.com/community/requests/design?sort=latest",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("tbody tr")
            for card in cards:
                tds = card.select("td")
                if len(tds) < 2:
                    continue
                title_td = tds[1]
                title_el = title_td.select_one("a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                link  = title_el.get("href", "")
                if link and not link.startswith("http"):
                    link = "https://khamsat.com" + link
                desc = ""
                budget = "غير محدد"
                jid       = hashlib.md5(link.encode()).hexdigest()
                jobs.append({"id": jid, "title": title, "desc": desc, "link": link, "budget": budget, "platform": "khamsat"})
        except Exception as e:
            logger.error(f"[khamsat] scrape error: {e}")
    return jobs


def scrape_kafeel() -> list[dict]:
    """
    Two correct platforms:
    - kafiil.com  (منصة كاف)
    - kafeel.sa   (منصة كفيل السعودية)
    """
    jobs = []
    sources = [
        ("https://kafiil.com/projects?sort=newest",                      "https://kafiil.com"),
        ("https://kafiil.com/projects?category=programming&sort=newest",  "https://kafiil.com"),
        ("https://kafiil.com/projects?category=design&sort=newest",       "https://kafiil.com"),
        ("https://kafeel.sa/projects?sort=newest",                        "https://kafeel.sa"),
    ]
    for url, base in sources:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select(".project-item, .project-card, article, tr.project, .job-card")
            for card in cards:
                title_el = card.select_one("h2 a, h3 a, .project-title a, a.title")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                link  = title_el.get("href", "")
                if link and not link.startswith("http"):
                    link = base + link
                desc_el   = card.select_one("p, .description, .brief")
                desc      = desc_el.get_text(strip=True) if desc_el else ""
                budget_el = card.select_one(".price, .budget")
                budget    = budget_el.get_text(strip=True) if budget_el else "غير محدد"
                jid       = hashlib.md5(link.encode()).hexdigest()
                jobs.append({"id": jid, "title": title, "desc": desc, "link": link, "budget": budget, "platform": "kafeel"})
        except Exception as e:
            logger.error(f"[kafeel] scrape error for {url}: {e}")
    return jobs


def scrape_nafzly() -> list[dict]:
    jobs = []
    urls = [
        "https://nafezly.com/projects?sort=latest",
        "https://nafezly.com/projects?category=programming&sort=latest",
        "https://nafezly.com/projects?category=design&sort=latest",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select('a[href*="/project/"]')
            for card in cards:
                title = card.get_text(strip=True)
                link  = card.get("href", "")
                if link and not link.startswith("http"):
                    link = "https://nafezly.com" + link
                desc = ""
                budget = "غير محدد"
                jid       = hashlib.md5(link.encode()).hexdigest()
                jobs.append({"id": jid, "title": title, "desc": desc, "link": link, "budget": budget, "platform": "nafzly"})
        except Exception as e:
            logger.error(f"[nafzly] scrape error: {e}")
    return jobs

# ─── MOSTAQL DM MONITOR ────────────────────────────────────────────────────────

mostaql_session = requests.Session()
mostaql_logged_in = False


def mostaql_login():
    global mostaql_logged_in
    if not MOSTAQL_EMAIL or not MOSTAQL_PASSWORD:
        return False
    try:
        # Get CSRF token
        r = mostaql_session.get("https://mostaql.com/login", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        token_el = soup.select_one('input[name="Norhan_amr"]')
        if not token_el:
            logger.warning("[mostaql DM] Could not find CSRF token")
            return False
        token = token_el["value"]

        # Login
        payload = {
            "_token": token,
            "email": MOSTAQL_EMAIL,
            "password": MOSTAQL_PASSWORD,
        }
        r2 = mostaql_session.post(
            "https://mostaql.com/login",
            data=payload,
            headers={**HEADERS, "Referer": "https://mostaql.com/login"},
            timeout=15,
            allow_redirects=True,
        )
        if "logout" in r2.text or "dashboard" in r2.url:
            mostaql_logged_in = True
            logger.info("[mostaql DM] Logged in successfully")
            return True
        else:
            logger.warning("[mostaql DM] Login failed — check credentials")
            return False
    except Exception as e:
        logger.error(f"[mostaql DM] Login error: {e}")
        return False


def check_mostaql_dms(seen_dms: set) -> list[dict]:
    global mostaql_logged_in
    new_dms = []

    if not MOSTAQL_EMAIL or not MOSTAQL_PASSWORD:
        return []

    if not mostaql_logged_in:
        if not mostaql_login():
            return []

    try:
        r = mostaql_session.get(
            "https://mostaql.com/messages",
            headers=HEADERS,
            timeout=15,
        )
        soup = BeautifulSoup(r.text, "html.parser")

        # Parse conversation list
        convs = soup.select(".conversation-item, .message-item, li.thread, .inbox-item")
        for conv in convs:
            sender_el = conv.select_one(".sender-name, .username, strong, .name")
            preview_el = conv.select_one(".message-preview, .preview, p, .last-message")
            link_el = conv.select_one("a")

            sender  = sender_el.get_text(strip=True) if sender_el else "مجهول"
            preview = preview_el.get_text(strip=True) if preview_el else ""
            link    = link_el.get("href", "") if link_el else ""
            if link and not link.startswith("http"):
                link = "https://mostaql.com" + link

            dm_id = hashlib.md5((sender + preview).encode()).hexdigest()
            if dm_id not in seen_dms:
                seen_dms.add(dm_id)
                new_dms.append({"sender": sender, "preview": preview, "link": link})

    except Exception as e:
        logger.error(f"[mostaql DM] Check error: {e}")
        mostaql_logged_in = False   # force re-login next time

    return new_dms

# ─── MESSAGE FORMATTING ────────────────────────────────────────────────────────

def format_job(job: dict, category: str) -> str:
    platform_label = PLATFORMS.get(job["platform"], job["platform"])
    return (
        f"🔔 <b>مشروع جديد!</b>  {platform_label}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{category}\n\n"
        f"📌 <b>{job['title']}</b>\n\n"
        f"📝 {job['desc'][:300]}{'...' if len(job['desc']) > 300 else ''}\n\n"
        f"💰 الميزانية: {job['budget']}\n"
        f"🔗 <a href='{job['link']}'>عرض المشروع</a>\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )


def format_dm(dm: dict) -> str:
    return (
        f"💬 <b>رسالة جديدة على مستقل!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 من: <b>{dm['sender']}</b>\n\n"
        f"📩 {dm['preview'][:300]}\n\n"
        f"🔗 <a href='{dm['link']}'>فتح المحادثة</a>\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

# ─── MAIN LOOP ─────────────────────────────────────────────────────────────────

def run():
    logger.info("🤖 Bot started — monitoring all platforms...")

    platforms_active = "، ".join(PLATFORMS.values())
    cats_active      = "\n".join(f"  • {c}" for c in KEYWORDS.keys())
    dm_status        = "✅ مفعّل" if MOSTAQL_EMAIL else "❌ غير مفعّل (أضف MOSTAQL_EMAIL و MOSTAQL_PASSWORD)"

    send_telegram(
        f"✅ <b>البوت يعمل الآن!</b>\n\n"
        f"📡 المنصات: {platforms_active}\n\n"
        f"🎯 الفئات:\n{cats_active}\n\n"
        f"💬 مراقبة رسائل مستقل: {dm_status}\n\n"
        f"🔄 كل فحص كل {CHECK_INTERVAL} ثانية"
    )

    seen_jobs = load_json(SEEN_FILE)
    seen_dms  = load_json(SEEN_DMS_FILE)

    scrapers = [scrape_mostaql, scrape_khamsat, scrape_kafeel, scrape_nafzly]

    while True:
        try:
            logger.info("─── Checking all platforms ───")

            # ── Jobs ──
            all_jobs = []
            for scraper in scrapers:
                jobs = scraper()
                print(f"{scraper.__name__}: {len(jobs)} jobs")
                all_jobs.extend(jobs)

            new_jobs = 0
            for job in all_jobs:
                if job["id"] in seen_jobs:
                    continue
                category = get_matching_category(job["title"], job["desc"])
                if not category:
                    seen_jobs.add(job["id"])   # mark seen even if not matching
                    continue
                seen_jobs.add(job["id"])
                send_telegram(format_job(job, category))
                new_jobs += 1
                time.sleep(1)

            save_json(SEEN_FILE, seen_jobs)
            logger.info(f"Jobs done. {new_jobs} new matching job(s).")

            # ── DMs ──
            new_dms = check_mostaql_dms(seen_dms)
            for dm in new_dms:
                send_telegram(format_dm(dm))
                time.sleep(1)
            if new_dms:
                save_json(SEEN_DMS_FILE, seen_dms)
            logger.info(f"DMs done. {len(new_dms)} new message(s).")

        except Exception as e:
            logger.error(f"Main loop error: {e}")

        time.sleep(CHECK_INTERVAL)


def debug():
    """Run once and print what each scraper finds, without sending Telegram messages."""
    print("=== DEBUG MODE ===")
    scrapers = {
        "mostaql":  scrape_mostaql,
        "khamsat":  scrape_khamsat,
        "kafeel":   scrape_kafeel,
        "nafzly":   scrape_nafzly,
    }
    for name, scraper in scrapers.items():
        print(f"\n--- {name} ---")
        jobs = scraper()
        print(f"  Found {len(jobs)} job(s)")
        for j in jobs[:3]:
            cat = get_matching_category(j["title"], j["desc"])
            print(f"  [{cat or 'NO MATCH'}] {j['title'][:80]}")
            print(f"  Link: {j['link']}")
    print("=== END DEBUG ===")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        debug()
    else:
        run()