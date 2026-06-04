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
