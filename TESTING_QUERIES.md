# KisanBot Testing Queries (Implemented Features)

## Feature Count (Current)

- PDF total features: **16**
- Implemented and testable now: **12**
- Pending/not fully done: **4**

Implemented 12 features:

1. Scheme chatbot (live API)
2. Mausam jankari (live API)
3. Mandi bhav (live API)
4. Fasal advice (RAG)
5. Telegram bot
6. Email notifications
7. Farmer profile DB
8. Conversation history DB
9. Alert history DB
10. Crop disease detector (image flow)
11. Soil health advisor (RAG)
12. Mandi price trend prediction (ML + graph)

Pending 4:

- Loan & subsidy finder (dedicated RAG dataset + flow)
- Pest alert system (weekly scheduled Telegram + email broadcast)
- Voice input (Telegram voice note + Whisper)
- Live scheme scraper / auto-update pipeline

---

## Telegram End-to-End Test Queries

Run bot first:

```bash
cd /home/gopi/Desktop/farmer_bot
uv run main.py telegram
```

Then send these in Telegram chat (same order recommended):

### 1) Start Bot

```text
/start
```

### 2) Profile Save (DB write)

```text
Mera naam Gopi hai, shehar Ahmedabad, fasal gehun, email gopikotadiya2002@gmail.com profile save karo.
```

### 3) Profile Read (DB read)

```text
Meri profile dikhao
```

### 4) Weather (Live API)

```text
Ahmedabad ka aaj ka mausam batao
```

### 5) Mandi Live Rates

```text
Amreli ka kapas ka bhav batao
```

### 6) Scheme Search

```text
PM Kisan Yojana ki details batao
```

### 7) Fasal RAG

```text
Gehun ki beej bowaai aur paani dene ka sahi tareeka batao
```

### 8) Pest RAG

```text
Kapas me safed makhi ka ilaaj kya hai
```

### 9) Soil RAG

```text
Mitti ka pH kam ho to kya karna chahiye
```

### 10) Farming Tips RAG

```text
Paani bachane ke best kheti tips batao
```

### 11) Crop Disease Image Detection

```text
Telegram me crop photo bhejo + caption: Is fasal me kaunsi bimari hai?
```

### 12) Daily Digest (Email + alerts table)

```text
/digest
```

Expected: Email aayega + alerts table me entry save hogi.

### 13) Mandi Trend Prediction (ML + graph)

```text
Muje amreli ka kapas ka next 7 days ka prediction do
```

Expected: Text forecast + graph image.

---

## Optional API Test Queries (Postman/curl)

Base:

```bash
BASE="http://localhost:8000/v1/kisan/chat"
SID="1791197250"
```

Profile save:

```bash
curl -s -X POST "$BASE" -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID\",\"text\":\"Mera naam Gopi, Ahmedabad, fasal gehun, email gopikotadiya2002@gmail.com profile save karo\"}"
```

Weather:

```bash
curl -s -X POST "$BASE" -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID\",\"text\":\"Ahmedabad ka mausam batao\"}"
```

Mandi live:

```bash
curl -s -X POST "$BASE" -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID\",\"text\":\"Amreli cotton mandi bhav batao\"}"
```

Mandi trend:

```bash
curl -s -X POST "$BASE" -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID\",\"text\":\"Amreli cotton ka next 7 days mandi trend prediction do\"}"
```

---

## DB Verification Commands

Recent profile row:

```bash
cd /home/gopi/Desktop/farmer_bot
sqlite3 db/kisanbot.db "SELECT id, session_id, telegram_id, name, location, crops, email, created_at FROM farmers ORDER BY id DESC LIMIT 5;"
```

Conversation history:

```bash
sqlite3 db/kisanbot.db "SELECT id, session_id, role, substr(content,1,80), timestamp FROM conversation_history ORDER BY id DESC LIMIT 10;"
```

Alerts history:

```bash
sqlite3 db/kisanbot.db "SELECT id, telegram_id, alert_type, substr(message,1,80), sent_at FROM alerts ORDER BY id DESC LIMIT 10;"
```
