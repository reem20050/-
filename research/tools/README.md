# tools/straddle_ev.py

מנוע EV/breakeven/Kelly **פרמטרי ו-instrument-agnostic** ל-long straddle המונע ע"י סיגנל
"will-it-move". ספריית תקן בלבד (`math`, `random`, `argparse`, `dataclasses`) — **ללא תלויות**.

## למה הוא קיים
כדי להפוך כל מסקנה במחקר למספר שאפשר לבדוק. הוא ממש את התזה: `straddle ≈ E|move|`, ולכן
`EV ≈ E[|move| | signal] − premium − costs`.

## תת־פקודות

| פקודה | מה היא עושה |
|---|---|
| `implied` | אומד מחיר straddle (BS מדויק + קירוב 0.8·S·σ·√T) ותנועה גלומה (`E|move|`, 1σ) מ-IV |
| `ev` | EV מ-precision + תנועה מותנית (`mu-hit`, `mu-miss`); נותן גם את הרף הנדרש |
| `required` | פותר ל-`mu_hit*` שמאפס את ה-EV — "כמה גדולה צריכה התנועה ב-hit?" |
| `mc` | Monte-Carlo מהתפלגות `|move|` מלאה: EV, win-rate, אחוזונים, P(הפסד מלא), ו-Kelly (`--kelly`) |

## דוגמאות
```bash
python straddle_ev.py implied  --S 4490 --iv 0.245 --minutes 120 --basis gold24x5
python straddle_ev.py implied  --S 30660 --iv 0.232 --minutes 60  --basis equity
python straddle_ev.py ev        --premium 16.3 --cost 0.4 -p 0.75 --mu-hit 35 --mu-miss 8 --strike 4490
python straddle_ev.py required  --premium 16.3 --cost 0.4 -p 0.75 --mu-miss 8
python straddle_ev.py mc        --premium 16.3 --cost 0.4 -p 0.75 --hit-mean 35 --hit-cv 0.8 --miss-mean 8 --kelly
```

## בסיסי זמן (`--basis`) — חשוב
תנודתיות מתכווננת ב-√זמן; הבסיס קובע כמה דקות בשנה:
- `calendar` — 24×7 (525,600 דק'/שנה) — לשווקים ~24 שעות אם ה-IV מצוטט כך
- `equity` — זמן־מסחר RTH (252×390) — מדדי/מניות ארה״ב
- `gold24x5` — ~23ש'×252 — זהב COMEX
- `fx24x5` / `equity24` — 24ש'×252

**בספק — הזן את ה-premium האמיתי מהשרשרת (`--premium`) במקום לאמוד מ-IV.** זה עוקף לגמרי את
סוגיית כיול הזמן ומשתמש במחיר השוק עצמו.

## הרחבה
- כל הפונקציות (`bs_price`, `atm_straddle_price`, `expected_abs_move`, `straddle_ev`,
  `straddle_ev_mc`, `kelly_fraction`) ניתנות לייבוא כמודול: `from straddle_ev import straddle_ev`.
- לחיבור ל-backtest אמיתי (מסמך `../07-backtesting.md`): הזן `premium` ו-`cost` מ-quotes אמיתיים
  (ask בכניסה, bid ביציאה), והשווה את `mean net PnL` של ה-backtest ל-EV התיאורטי.

---

# optimize_threshold_horizon.py — Optuna על threshold ו-horizon

חיפוש Optuna על `(X, N)` שבנוי **לעמוד בפני overfitting**. שני עקרונות מובנים:
1. **האובייקטיב = P&L נטו OOS אחרי עלויות (Sharpe/net_ev/Calmar)** — לא precision.
2. **הגנות overfitting בכל שכבה:** walk-forward + embargo בתוך כל trial; הסף בפרמטר **σ-units**
   (`X = k · implied_move(N)` — מנתק את צימוד `X ~ √N`); **Deflated Sharpe** מול מספר ה-trials;
   בדיקת **plateau** (האופטימום חייב להיות מוקף בשכנים טובים); ו-**holdout** ש-Optuna לא רואה.

**להרצה (דמו סינתטי — נתונים מזויפים, להדגמת המנגנון):**
```bash
pip install optuna numpy pandas
python optimize_threshold_horizon.py --demo --trials 60 --objective sharpe
```

**לשימוש אמיתי — שני hooks למלא (מסומנים `# === PLUG IN ===`):**
- `predicted_move(df, horizon_min)` — פלט המודל שלך (תחזית `|move|` לחלון). מודל מגניטודה/quantile
  (מסמך `../04`) חוסך אימון מחדש לכל X. classifier בינארי → אמן מחדש כאן ו-cache.
- `straddle_pnl_from_quotes(entry_ts, horizon_min, ctx)` — P&L נטו מ-**quotes אמיתיים** (קנה ב-ask,
  מכור ב-bid, פחות עמלות). זו הדרך **היחידה** לתפוס theta/gamma/IV-crush/spread אמיתיים; ה-IV
  המודלי הוא fallback ל-wiring בלבד, לא להחלטות.

**פלט:** הפרמטרים הטובים, יציבות plateau, מדדי holdout, ו-DSR (>0.95 = כנראה אמיתי; <0.9 = כנראה רעש).
