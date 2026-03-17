# 🤖 مستقل Job Alert Bot

يراقب هذا البوت موقع **مستقل** تلقائياً ويرسل إشعار فوري على Telegram عند نزول مشروع جديد في مجال:
- 🧠 الذكاء الاصطناعي (AI / ML)
- 💻 البرمجة والتطبيقات
- 🌐 تطوير المواقع

---

## ⚙️ الإعداد (خطوتان فقط)

### الخطوة 1 — إنشاء بوت Telegram

1. افتح Telegram وابحث عن **@BotFather**
2. أرسل `/newbot` واتبع التعليمات
3. انسخ الـ **Token** الذي يعطيك إياه

### الخطوة 2 — الحصول على Chat ID

1. ابحث عن **@userinfobot** في Telegram
2. أرسل له `/start`
3. انسخ الـ **ID** الخاص بك

---

## 🚀 التشغيل

### طريقة 1 — Python مباشرة

```bash
# تثبيت المكتبات
pip install -r requirements.txt

# تعيين المتغيرات
export TELEGRAM_TOKEN="123456:ABC-your-token"
export CHAT_ID="123456789"

# تشغيل البوت
python bot.py
```

### طريقة 2 — Docker (موصى به للسيرفر)

```bash
# أنشئ ملف .env
echo "TELEGRAM_TOKEN=123456:ABC-your-token" > .env
echo "CHAT_ID=123456789" >> .env

# شغّل
docker-compose up -d

# تابع اللوج
docker-compose logs -f
```

---

## ⚙️ الإعدادات

في ملف `bot.py` يمكنك تعديل:

| المتغير | الوصف | الافتراضي |
|---------|-------|-----------|
| `CHECK_INTERVAL` | كم ثانية بين كل فحص | 120 ثانية |
| `KEYWORDS` | الكلمات المفتاحية للفلترة | AI، برمجة، موقع... |

---

## 📁 الملفات

```
mostaql_bot/
├── bot.py              # الكود الرئيسي
├── requirements.txt    # المكتبات
├── Dockerfile          
├── docker-compose.yml  
└── seen_jobs.json      # يُنشأ تلقائياً (المشاريع المرئية)
```
