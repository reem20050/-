# Workflow חקירה מעמיק — מונטיזציה של סיגנל "תהיה תנועה" באמצעות אופציות (long straddle)

> **מה זה:** תוכנית חקירה **פרמטרית** וניתנת־להרצה־מחדש שמכריעה שאלה אחת —
> *האם, ואיך, אפשר להפוך סיגנל ML שמנבא "תנועה ≥ X בתוך N דקות" (precision ~75%)
> לכסף, בעיקר דרך long straddle* — עבור **כל** נכס (זהב, נאסד״ק, ...), כל סף X וכל חלון N.
>
> זה לא דוח חד־פעמי. זו מערכת: פירוק לשאלות → פיזור עשרות סוכני מחקר → אימות יריב → סינתזה →
> שערי החלטה (go/no-go) → ביצוע. המסמך הזה הוא ה"מנוע"; התוצרים יושבים תחת `research/`.

---

## 0. פרמטריזציה — מה מזינים

```
SIGNAL = (instrument, X, N, p, side)
  instrument : הנכס (Gold/GC/GLD, NDX/NQ/QQQ, ...)
  X          : סף התנועה (לדוגמה $25 לזהב, 150 נק' לנאסד״ק)
  N          : חלון הזמן בדקות (120 / 60 / ...)
  p          : precision על המחלקה החיובית (~0.75 = "כשאומר תנועה, צודק ב-75%")
  side       : magnitude-only (ברירת מחדל) או יש lean כיווני
```

ה-workflow כולו רץ כפונקציה של ה-tuple הזה. הדוגמאות (זהב $25/120 ונאסד״ק 150/60) הן שתי
הרצות של אותו מנוע.

---

## 1. השאלה המרכזית שה-workflow מכריע

> **long straddle אינו רווחי כי "קרתה תנועה" — אלא רק אם התנועה הממומשת גדולה ממה ששולם.**

מכאן נגזרות שלוש שאלות־על שה-workflow חייב לענות עליהן במספרים, לא במילים:

1. **תמחור:** כמה עולה ה-straddle ל-`(instrument, N)`, וכמה גדולה התנועה הגלומה (`E|move|_implied`)?
2. **edge:** האם `E[|move| | signal]` (התנועה הממומשת המותנית בסיגנל) גדולה מהמחיר הזה + ה-VRP + חיכוך?
3. **שרידוּת:** האם ה-75% ישרוד בלייב (אין leakage/overfitting), והאם הגודל/הסיכון שורדים את ה-25% המפסידים?

אם שלושתן "כן" עם margin — יש אסטרטגיה. אם אחת "לא" — אין, ולא משנה כמה הסיגנל מרשים.

---

## 2. התזה הכמותית (העוגן של כל הסוכנים)

```
straddle_ATM  ≈  0.7979 · S · σ · √T  ≈  E|move|_implied         (★ ה-identity)
EV(straddle)  ≈  E|move|_realized|signal  −  straddle  −  costs   (♦ הרווח = פער RV מול IV)
b+EV  ⇔  E[|move| | signal]  >  D + costs                         (♣ הרף)
```

נגזרת מלאה, אישושים מספריים ודוגמאות עובדות: `research/03-core-profitability-model.md`.
כל מספר ניתן לשחזור עם `research/tools/straddle_ev.py`.

---

## 3. פירוק ל-Workstreams — מצבת הסוכנים ("עשרות הסוכנים")

ה-workflow מפרק את הבעיה ל-**20 תתי־שאלות** עצמאיות, וכל אחת נחקרת ע"י סוכן ייעודי עם web,
חוזה־פלט אחיד (תקציר → פירוט → מספרים/נוסחאות → מקורות מצוטטים) וכלל **אימות מ-≥2 מקורות**.
שני גלים מקבילים:

### גל A — ליבה (12 סוכנים)
| # | Workstream | שאלת המפתח | מסמך יעד |
|---|---|---|---|
| A1 | Straddle mechanics & Greeks | payoff, breakevens, gamma-theta PDE, ה-0.7979 | 02, 03 |
| A2 | Volatility Risk Premium | כמה IV>RV, והרף שצריך לעבור | 03, 05 |
| A3 | 0DTE / short-dated | אילו מכשירים, theta/gamma לחלון של שעתיים | 05 |
| A4 | IV crush & events vs surprise | למה straddle לתוך אירוע מפסיד; regime A מול B | 05 |
| A5 | Strategy landscape | strangle/guts/backspread/short-premium — מתי כל אחד | 02 |
| A6 | Gold market mapping | מיפוי $25 לחוזים, GVZ, תנועה גלומה | 06 |
| A7 | NASDAQ market mapping | מיפוי 150 נק', VXN, תנועה גלומה | 06 |
| A8 | Microstructure & costs | spread כפול, חיכוך round-trip כ-% מהפרמיה | 05 |
| A9 | Backtesting methodology | נתונים, מלכודות, purged CV, DSR, loop | 07 |
| A10 | Signal → EV & Kelly | precision≠win-rate; מה לבקש מה-ML; fractional Kelly | 04 |
| A11 | ML validity | leakage/overfitting/regime — האם 75% ישרוד | 04, 08 |
| A12 | Adversarial (devil's advocate) | למה קוני straddle מפסידים; הרף הכן | 08 |

### גל B — העמקה (8 סוכנים)
| # | Workstream | שאלת המפתח | מסמך יעד |
|---|---|---|---|
| B1 | Gamma scalping | קצירת RV דרך delta-hedging; מתי עדיף על hold | 02, 08 |
| B2 | Intraday seasonality | מתי ביום מהלכים גדולים (זהב/נאסד״ק); base rates | 05, 06 |
| B3 | Live execution & automation | broker APIs, combo orders, pipeline, kill-switch | 08 |
| B4 | Tax (1256 vs equity) | 60/40 ל-NDX/GC מול short-term ל-GLD/QQQ | 06, 08 |
| B5 | Portfolio risk & ruin | drawdown, risk-of-ruin, מגבלות תיק | 08 |
| B6 | Meta-labeling & signal upgrade | triple-barrier, magnitude head, calibration | 04 |
| B7 | Case studies & academia | Goyal-Saretto וכו' — האם edge גובר על VRP | 08 |
| B8 | Direct vol trading | variance swaps / VIX·GVZ — למה לרוב לא מתאים | 02 |

> **למה כל כך הרבה סוכנים:** כל workstream דורש מקורות וניואנסים שונים (specs בורסה, מאמרים,
> מתודולוגיה). פיזור מקבילי = עומק אמיתי + מהירות, וכל טענה כמותית מאומתת בנפרד.

---

## 4. מתודולוגיה — fan-out → verify → synthesize

1. **Decompose** — את ה-tuple לשאלות ה-workstream שלמעלה.
2. **Fan-out** — סוכן לכל workstream, במקביל, עם web + חוזה־פלט אחיד.
3. **Adversarial verify** — כל מספר קריטי מאומת מ-≥2 מקורות; סוכן A12 הוא devil's advocate ייעודי;
   אי־ודאות מסומנת במפורש (flag) ולא מוסתרת.
4. **Synthesize** — אינטגרציה למסמכים `research/02..08`, עם ביבליוגרפיה מאוחדת (`research/sources.md`).
5. **Quantify** — כל מסקנה מתורגמת למספרים דרך `straddle_ev.py` (EV, breakeven, required edge, Kelly).
6. **Gate** — מעבר דרך שערי ההחלטה (סעיף 5) לפני כל סיכון הון.

**תקני איכות:** מקורות סמכותיים (CBOE/CME/OIC, מאמרים אקדמיים, ברוקרים מבוססים); תיארוך כל רמת
שוק; הפרדה בין "מוכח" ל"מותנה בהנחה"; שום padding.

---

## 5. שערי החלטה (Go / No-Go) — לפני שמסכנים שקל

הרץ בסדר; כישלון בשער = עצור או חזור ל-ML team.

```
G1  תמחור     : חשב D ו-E|move|_implied מה-chain האמיתי (לא תיאורטי).
                האם X גדול מ-D? אם X << D → הסיגנל מנבא רעש, פסול.   [straddle_ev.py implied]

G2  edge      : השג מה-ML team את E[|move| | hit] ואת mu_hit*.
                האם E[|move| | hit] >> required mu_hit עם margin?     [straddle_ev.py required/ev]
                אם לא → אין edge, עצור.

G3  regime    : האם הסיגנלים מתרכזים סביב אירועים (IV מנופח, IV crush)?
                מדוד IV%ile ברגע הסיגנל. אם חציון > 65 → regime A מסוכן.   [מסמך 05]

G4  validity  : האם ה-75% שרד purged/embargoed CV + walk-forward + DSR?
                האם אין leakage? (audit timestamps)                  [מסמך 04, 11]
                אם לא → ה-75% אשלייתי, עצור.

G5  costs     : האם ה-EV חיובי אחרי חיכוך round-trip אמיתי (~3-15% מהפרמיה)?  [מסמך 05, 08]

G6  backtest  : EV חיובי על נתוני אופציות תוך־יומיים אמיתיים, OOS, ≥200 עסקאות,
                fills ב-ask/bid (לא mid)?                             [מסמך 07]

G7  risk      : fractional Kelly (¼-½), per-trade ≤1-2%, daily loss limit,
                סימולציית ruin עוברת?                                 [מסמך 08, 05]

G8  paper     : forward/paper-trading תואם את ה-backtest לפני הון אמיתי?  [מסמך 08]
```

רק מי שעובר את **כל** השערים מצדיק הון אמיתי, ואז בגודל קטן ומדורג.

---

## 6. Runbook — איך מריצים מחדש לנכס/סיגנל חדש

```
1. הגדר SIGNAL = (instrument, X, N, p, side).
2. משוך מה-chain: spot S, IV/את ה-ATM straddle premium D, ומבנה ה-expiries הקצר ביותר.
3. python research/tools/straddle_ev.py implied --S <S> --iv <IV> --minutes <N> --basis <basis>
   → קבל E|move|_implied ו-1σ. השווה ל-X (כמה σ זה X?).
4. בקש מה-ML team: base rate, recall, ובעיקר התפלגות |move| בהינתן סיגנל (לפחות הממוצע).
5. python research/tools/straddle_ev.py required ...   → mu_hit* (הרף).
   python research/tools/straddle_ev.py ev / mc ...    → EV, win-rate, Kelly.
6. עבור על שערי G1–G8 (סעיף 5). תעד כל שער ב-research/.
7. אם עברת הכל → בחר מכשיר (06) + מבנה (02) + expiry (05), הגדר playbook (08), ואז paper-trade.
8. אם נכשלת בשער → חזור ל-ML team עם הבקשה הספציפית (מסמך 04) או פסול את הסיגנל לנכס הזה.
```

מכשירים שמופו כבר: **זהב** (GC/MGC/GLD, GVZ≈24, $25≈1.25–1.6σ ל-120 דק') ו**נאסד״ק-100**
(NDX/NQ/QQQ, VXN≈23, 150נק'≈0.85σ ל-60 דק' בבסיס RTH הסטנדרטי — מהלך נפוץ, לא tail).
ראה `research/06-instruments.md` למיפוי מלא ולרגישות בסיס־הזמן.

---

## 7. מפת התוצרים

```
workflows/
  research-workflow.md   ← אתה כאן (המנוע: פירוק, סוכנים, מתודולוגיה, שערים, runbook)
  README.md              ← התמצאות מהירה
research/
  README.md              ← תקציר מנהלים (עברית) + מדריך קריאה + שימוש בכלי
  02-strategy-landscape.md
  03-core-profitability-model.md   ← הליבה המתמטית
  04-signal-to-edge.md
  05-volatility-events-execution.md
  06-instruments.md
  07-backtesting.md
  08-risks-and-playbook.md
  sources.md             ← ביבליוגרפיה מאוחדת (כל המקורות המצוטטים)
  tools/
    straddle_ev.py       ← מנוע EV/breakeven/Kelly פרמטרי (stdlib בלבד)
    README.md
```

---

## 8. שורה תחתונה של ה-workflow

הסיגנל שלך (precision 75% על "תנועה") הוא **תנאי הכרחי ומבטיח** — אבל ה-workflow קיים כדי
לוודא שהוא גם **מספיק**. ההכרעה לא נופלת על אחוז ה-precision, אלא על **שלושה מספרים** שצריך
להוציא ולאמת: (1) `D` — המחיר; (2) `E[|move| | hit]` — גודל התנועה המותנית; (3) שרידוּת ה-75%
בלייב. ה-workflow הזה הוא הדרך השיטתית לקבל את שלושתם, עם עשרות מקורות מאחורי כל קביעה.
