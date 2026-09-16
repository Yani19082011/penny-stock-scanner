# Penny Stock Scanner

Фаза 1 от плана за двата бота (виж design документа). Сканира US акции ≤ $20,
пресмята confluence score от технически индикатори + новинарски catalyst,
поддържа персистентен watchlist от до 5 тикера и праща алърт при висок
потенциал.

**Реално-времева версия:** два цикъла - бърз (`FAST_INTERVAL_MINUTES`, по
подразбиране 2 мин) прескорира само вече наблюдаваните 5 тикера за бърз
алърт, докато по-бавен пълен scan (`SCAN_INTERVAL_MINUTES`, по подразбиране
10 мин) търси нови кандидати за целия universe. Алърт за "висок потенциал"
се праща само при ново пресичане на прага, не на всеки цикъл докато тикерът
си стои горе.

**Важно:** това НЕ изпълнява поръчки автоматично - само генерира сигнали/алърти.
Не е финансов съвет.

## 1. Локално пускане (тест преди deploy)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Отвори `.env` и попълни:

1. **ALPACA_API_KEY / ALPACA_SECRET_KEY** — от https://app.alpaca.markets/paper/dashboard/overview → "View API Keys" (вече имаш paper акаунт).
2. **FINNHUB_API_KEY** — регистрация на https://finnhub.io/register → Dashboard → "API key" (безплатно, ~60 requests/min лимит).
3. **FMP_API_KEY** — регистрация на https://site.financialmodelingprep.com/register → Dashboard → "API Key" (безплатен tier, ограничен брой заявки/ден — виж техния dashboard за точния лимит).

Без FMP ключ скенерът пак работи, но пада на статичен fallback списък акции
(виж `universe.py`) вместо да сканира целия пазар.

Пускане:

```bash
python main.py
```

Ще видиш логове в конзолата всеки `SCAN_INTERVAL_MINUTES` минути (по подразбиране 15).

## 2. Backtest преди да разчиташ на живи сигнали

```bash
python backtest.py SIRI NOK SOFI PLUG FCEL --days 180
```

Извежда win rate, среден return, max loss за исторически сигнали. Прагът
`HIGH_POTENTIAL_THRESHOLD` в `scoring.py` трябва да се коригира спрямо тези
резултати, а не да се приема на доверие.

**Ограничения на backtest-а:** ползва безплатни дневни данни от Yahoo Finance
(`yfinance`) — достатъчно за груба преценка на логиката, но не заменя истински
intraday backtest с новини/catalyst данни назад във времето (безплатните
tier-ове на Finnhub/FMP не покриват дълбока историческа новинарска база).
Приемай резултатите като насока, не като гаранция.

## 3. Deploy на Railway (auto-deploy при git push, както Confluence Bot)

1. Качи тази папка като нов GitHub repo (напр. `penny-stock-scanner`):
   ```bash
   git init
   git add .
   git commit -m "Initial penny stock scanner"
   git branch -M main
   git remote add origin https://github.com/<твоя-username>/penny-stock-scanner.git
   git push -u origin main
   ```
2. В Railway: New Project → Deploy from GitHub repo → избери repo-то.
3. Railway ще открие `Procfile` автоматично (worker процес — това НЕ е web service, така че не му трябва публичен URL/port).
4. Отиди в Railway → твоя service → **Variables** таб и добави същите ключове като в `.env` (ALPACA_API_KEY, ALPACA_SECRET_KEY, FINNHUB_API_KEY, FMP_API_KEY, и т.н.). **Никога не commit-вай `.env` файла** — `.gitignore`-ът вече го изключва.
5. Railway → Deployments → Logs, за да видиш дали цикълът тръгва и дали има грешки.

## 4. Email алърти през Resend (не Gmail SMTP)

Gmail "App Passwords" не работят на Family Link (supervised) акаунти, затова
ползваме [Resend](https://resend.com) — безплатна услуга, праща email през
обикновен HTTP API с ключ, без нужда от App Password/2FA проблеми.

1. Регистрирай се безплатно на resend.com (може със същия имейл, на който
   искаш да получаваш алъртите — напр. `yani.kolev2011@gmail.com`).
2. Dashboard → **API Keys** → **Create API Key** → копирай ключа (показва се само веднъж).
3. В Render → Environment таб (или локален `.env`):
   ```
   ALERT_EMAIL_ENABLED=true
   RESEND_API_KEY=<копирания ключ>
   RESEND_FROM_EMAIL=onboarding@resend.dev
   ALERT_EMAIL_TO=yani.kolev2011@gmail.com
   ```
   **Важно:** без верифициран собствен домейн в Resend, безплатният `onboarding@resend.dev`
   подател може да праща само до имейла, с който си се регистрирал в Resend —
   затова `ALERT_EMAIL_TO` трябва да съвпада с него.
4. Redeploy — оттук нататък алъртите за "висок потенциал" отиват и по имейл, не само в логовете.

## Структура на проекта

| Файл | Роля |
|---|---|
| `config.py` | Чете всички настройки от environment variables |
| `data_sources.py` | Alpaca / Finnhub / FMP / SEC EDGAR wrapper-и |
| `indicators.py` | EMA, VWAP, RSI, ORB breakout, S/R, свещникови модели |
| `scoring.py` | Confluence score формула + прагове |
| `universe.py` | Списък с кандидат-тикери (FMP screener или fallback) |
| `watchlist.py` | Персистентен watchlist от 5 тикера (JSON файл в `data/`) |
| `notifier.py` | Лог + email алърти |
| `backtest.py` | Офлайн тест на score логиката върху история |
| `main.py` | Главния scan loop (влиза в `Procfile`) |

## Следваща стъпка

Фаза 2 от плана: свързване на Gmail connector-а в Claude чата за реални email
алърти (вместо само лог), и после Фаза 3 — memecoin scanner бота.
