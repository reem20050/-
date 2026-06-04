# SFP Research — חקירת מערכת *Swing Failure Signals [AlgoAlpha]*

ערכת בקטסטינג בפייתון לחקירה שיטתית של אינדיקטור ה‑Pine
**Swing Failure Signals [AlgoAlpha]**. הקוד מבצע *פורט נאמן* של הלוגיקה מ‑Pine
ל‑Python, ומעליו בונה מנוע בקטסט, מטריקות ביצועים, סריקת פרמטרים וגרפים —
כך שאפשר לבדוק את המערכת על דאטה אמיתי (CSV / yfinance) או סינתטי.

> **שורה תחתונה מראש:** האינדיקטור המקורי רק *מצייר* סיגנלים — הוא לא מגדיר
> כניסה/סטופ/יעד. הערכה הזו מוסיפה מודל מסחר ריאלי מסביב לסיגנלים כדי שאפשר
> יהיה באמת *למדוד* האם יש בהם edge.

---

## 1. מה המערכת עושה (הסבר רעיוני)

המערכת היא בסגנון **ICT / Smart‑Money**. היא מחפשת **Swing Failure Pattern (SFP)** —
"ציד נזילות": המחיר חוצה קצה של סווינג קודם (high/low), מפעיל סטופים/נזילות
מעבר לו, ואז **נכשל** וחוזר פנימה. כדי לסנן את הרעש, הכשלון חייב לקבל אישור של
**Change in State of Delivery (CISD)** — שינוי במבנה השוק (סדרת נרות שמשנה כיוון).

* **Bullish SFP**: נזילות *מתחת* לסווינג‑לואו נטרפה (wick מתחת ללואו), ואז ה‑CISD
  אישר מעבר כלפי מעלה → סיגנל קנייה.
* **Bearish SFP**: נזילות *מעל* סווינג‑היי נטרפה, וה‑CISD אישר מעבר כלפי מטה →
  סיגנל מכירה.

---

## 2. פירוק האלגוריתם (צינור הסיגנל)

```
Pivots  ─▶  Sweep detection  ─▶  CISD confirmation  ─▶  Trend flip  ─▶  Signal
```

| שלב | מה קורה | פרמטר | קוד |
|-----|---------|--------|-----|
| **1. Pivots** | זיהוי סווינג high/low עם `ta.pivothigh/low(len,len)`. פיבוט מאושר `len` נרות אחרי שהתרחש. | `pivot_len` (12) | `pivot_high/low` |
| **2. Sweep** | אם ה‑`high` הנוכחי חוצה פיבוט‑היי שמור (תוך `max_edge` נרות) → sweep דובי. סימטרי ל‑`low` מול פיבוט‑לואו → sweep שורי. הפיבוט "נצרך" ונמחק מהמאגר. | `max_edge` (50) | בלוק *Sweep Detection* |
| **3. CISD** | מעקב אחרי נרות "היפוך" (נר דובי→שורי וההפך). אישור CISD דורש שהתגובה־הנגדית הייתה משמעותית ביחס לרגל הקודמת: `(retrace)/(leg) > tolerance`. | `tolerance` (0.7) | בלוק *CISD* |
| **4. Trend** | `cisd==1 → trend=-1`, `cisd==2 → trend=+1`. | — | `prev_trend/trend` |
| **5. Signal** | `bullsfp` = ה‑trend חצה מעל 0 **וגם** היה sweep שורי בתוך `patience` נרות. סימטרי ל‑`bearsfp`. | `patience` (7) | crossover/under |

הפלט: חיצים (`plotshape`), צביעת נרות, וקווים על הרמות שנטרפו ועל רמת ה‑CISD,
בתוספת `alertcondition` לכל כיוון.

> פירוט שורה‑אחר‑שורה של ההמרה מ‑Pine נמצא ב‑docstring של
> [`sfp/indicator.py`](sfp/indicator.py).

---

## 3. ה‑Workflow (מתודולוגיית החקירה)

המבנה תומך בלולאת חקירה בארבעה שלבים:

1. **שחזור (fidelity).** ודא שהפורט מייצר את אותם סיגנלים כמו ב‑TradingView.
   הרץ את האינדיקטור על אותו symbol/timeframe והשווה את מיקומי החיצים.
   ראה *הערות נאמנות* בסעיף 6.
2. **מדידה (baseline).** הרץ בקטסט בפרמטרי ברירת המחדל וקרא את המטריקות
   (`win_rate`, `expectancy_R`, `profit_factor`, `max_drawdown_pct`, ...).
   זה ה‑baseline שכל שינוי נמדד מולו.
3. **רגישות (sweep).** סרוק את מרחב הפרמטרים (`scripts/param_sweep.py`).
   חפש **אזורים רציפים** של ביצועים טובים — לא פסגה בודדת (סימן ל‑overfit).
4. **תיקוף (robustness).** בדוק out‑of‑sample (פצל את הדאטה), על מספר נכסים/
   טיים‑פריימים, ועם עלויות (`--fee-pct`). edge ששורד את כל אלה שווה משהו.

### השערות שכדאי לבדוק

- האם ה‑edge תלוי בעיקר ב‑`tolerance` (פילטר הרעש)?
- האם long ו‑short סימטריים? (`long_win_rate` מול `short_win_rate`).
- כיצד יחס הסיכון/סיכוי (`rr`) ממיר win‑rate לתוחלת? (יעד גבוה = win‑rate נמוך).
- האם `stop_mode="sweep"` (סטופ מעבר לקצה הנזילות) עדיף על `atr`/`pct`?
- מה ה‑`patience` האופטימלי — חלון קצר (סיגנל "טרי") מול ארוך (יותר סיגנלים)?

### מדדים והאזהרות שלהם

`expectancy_R` (תוחלת ב‑R ליחידת סיכון) הוא המדד המרכזי. `profit_factor>1`,
`max_drawdown_pct` סביר, ומספיק `n_trades` (≥30) נדרשים כדי לתת אמון. היזהר מ:
look‑ahead (לכן ברירת המחדל היא כניסה ב‑`next_open`), survivorship, ו‑overfit
בסריקה (תמיד תקף out‑of‑sample).

---

## 4. התקנה והרצה

```bash
pip install -r requirements.txt        # numpy, pandas (חובה); matplotlib, yfinance, pytest (אופציונלי)

# בקטסט על דאטה סינתטי (עובד אופליין, כולל בסביבת Claude Code web):
python scripts/run_backtest.py --source synthetic --bars 2500 --rr 2 --plot

# על ה‑CSV שלך (עמודות: date/open/high/low/close):
python scripts/run_backtest.py --source csv --csv data/BTCUSD_1h.csv --rr 2 --trades-csv out/trades.csv

# דרך yfinance (רק היכן ש‑Yahoo נגיש, למשל מחשב מקומי):
python scripts/run_backtest.py --source yfinance --ticker AAPL --period 5y

# סריקת פרמטרים:
python scripts/param_sweep.py --source synthetic --bars 3000 --top 15 --out-csv out/sweep.csv
```

### שימוש כספרייה

```python
from sfp import synthetic_ohlc, SFPParams, run_indicator
from sfp import BacktestConfig, run_backtest, compute_metrics, format_metrics

df  = synthetic_ohlc(2500, seed=7)          # או load_csv("path.csv")
res = run_indicator(df, SFPParams(pivot_len=12, max_edge=50, patience=7, tolerance=0.7))
bt  = run_backtest(res, BacktestConfig(stop_mode="sweep", target_mode="rr", rr=2.0))
print(format_metrics(compute_metrics(bt)))
```

---

## 5. ארכיטקטורת הקוד

```
sfp/
├── indicator.py   # פורט נאמן של ה‑Pine (state machine bar‑by‑bar) → סיגנלים
├── data.py        # load_csv / load_yfinance / synthetic_ohlc + נורמליזציה
├── backtest.py    # מנוע בקטסט: כניסה/סטופ/יעד/flip + ניהול הון מבוסס סיכון
├── metrics.py     # win‑rate, expectancy, profit factor, drawdown, Sharpe...
├── optimize.py    # grid_search עם cache לאינדיקטור + פונקציית ניקוד
└── plotting.py    # גרף סיגנלים + עקומת הון (Agg, ללא תצוגה)
scripts/           # run_backtest.py, param_sweep.py (CLI)
tests/             # pytest — נאמנות פיבוטים, סיגנלים, בקטסט, מטריקות
```

### מודל המסחר (`BacktestConfig`)

| הגדרה | ברירת מחדל | תיאור |
|-------|------------|-------|
| `entry` | `next_open` | כניסה בפתיחת הנר הבא (ללא look‑ahead) או בסגירת נר הסיגנל. |
| `stop_mode` | `sweep` | סטופ מעבר לקצה הנזילות שנטרף / `atr` / `pct`. |
| `target_mode` / `rr` | `rr` / 2.0 | יעד כפולת סיכון, או `opposite` (יציאה בסיגנל הפוך), או `none`. |
| `max_hold_bars` | 0 | סטופ‑זמן (0 = כבוי). |
| `risk_frac` | 0.01 | סיכון לעסקה כאחוז מההון → עקומת הון מתכנסת ב‑R. |
| `fee_pct` | 0.0 | עלות לכל צד (אחוז מהנוטיונל). |

---

## 6. הערות נאמנות (KNOWN FIDELITY NOTES)

הפורט שואף לדיוק מלא, אך כמה נקודות חשובות להבהיר:

1. **פיבוטים (`>` חמור):** `pivot_high/low` משתמשים בהשוואה חמורה משני הצדדים;
   שוויון מבטל פיבוט. זו הפרשנות הנפוצה ל‑`ta.pivothigh`, אך ייתכנו הבדלי קצה
   נדירים מול TradingView במצבי שוויון.
2. **`bar_index` של הפיבוט:** המקור שומר את אינדקס *האישור* (הנר הנוכחי) ולא את
   נר הפיבוט עצמו (`n - len`). שומרנו זאת זהה — זה משפיע על בדיקת המרחק `max_edge`.
3. **`real‑time` מול `bar‑close`:** הבקטסט מניח החלטות על *סגירת נר* (כמו
   `barstate.isconfirmed`). על TradingView ב‑real‑time סיגנלים עלולים להיצבע ואז
   להיעלם (repaint) תוך כדי הנר — הבקטסט לא משחזר את ההתנהגות התוך‑נרית הזו.
4. **התאמת מקור:** כדי לאמת מול TradingView, ייצא את אותו סימבול/טיים‑פריים ל‑CSV
   והשווה את מיקומי החיצים מול מספר הסיגנלים בפלט.

---

## 7. מגבלות ואזהרה

זהו כלי **מחקר/חינוך**, לא ייעוץ השקעות. תוצאות על דאטה סינתטי הן *להדגמת הצינור
בלבד* — לדאטה האקראי אין edge אמיתי, ולכן תוחלת שלילית שם היא תקינה וצפויה.
מסקנות אמיתיות דורשות דאטה שוק אמיתי, תיקוף out‑of‑sample, עלויות מסחר, והתחשבות
בהחלקה (slippage) ובמילוי הזמנות.

---

*Pine source © AlgoAlpha, Mozilla Public License 2.0. הפורט והערכה כאן הם
ריאימפלמנטציה לצורכי מחקר.*
