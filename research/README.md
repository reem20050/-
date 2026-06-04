# מחקר: מונטיזציה של סיגנל "תהיה תנועה" באמצעות Long Straddle

**תקציר מנהלים + מדריך קריאה.** זה הפלט של הרצת ה-workflow שב-`../workflows/research-workflow.md`
פעם אחת על הבעיה שלך: סיגנל ML שמנבא "תנועה ≥ X בתוך N דקות" עם ~75% precision, שאתה רוצה
להפוך לכסף — בעיקר דרך long straddle. ~20 סוכני מחקר עם מאות מקורות מצוטטים (`sources.md`).

---

## התובנה האחת (אם תקרא רק שורה אחת)

> **straddle ATM מתומחר בערך כמו התנועה־המוחלטת הצפויה:** `straddle ≈ 0.8·S·σ·√T ≈ E|move|`.
> לכן אתה מרוויח **רק** אם התנועה הממומשת גדולה מהמחיר ששילמת. ה-75% precision שלך הוא
> **הכרחי אבל לא מספיק** — מה שמכריע את ה-EV הוא **גודל התנועה בהינתן סיגנל**, לא ההסתברות הבינארית.

```
EV ≈ E[|move| | signal] − straddle_premium − costs
b+EV  ⇔  E[|move| | hit] > breakeven (≈ הפרמיה)
```

---

## הפסיקה (verdict): "מבטיח, מותנה — לא מוכח עדיין"

- ✅ **הכיוון נכון.** סטראדל הוא המבנה הנכון לסיגנל מגניטודה (כיוון לא ידוע). העדות האקדמית
  (Goyal-Saretto) מראה ש**edge מותנה־תחזית אכן יכול לגבור על ה-VRP** — בעיקר על נכסים בודדים.
- ⚠️ **שלוש רוחות נגדיות מבניות:** VRP (IV>RV ב-~85% מהזמן), IV crush סביב אירועים, וחיכוך כפול.
- ❌ **שלושה מספרים עוד חסרים** כדי להוכיח +EV. בלעדיהם, כל ה-+EV בדוגמאות *מותנה בהנחות*.

### שלושת המספרים שאתה חייב להשיג (זה ה-action item המרכזי)
1. **`D` — מחיר ה-straddle האמיתי** מהשרשרת ל-`(instrument, N)`, והתנועה הגלומה. [`straddle_ev.py implied`]
2. **`E[|move| | hit]` — גודל התנועה הממוצע כש"hit"**, מה-ML team. ⭐ זה הנתון הכי קריטי, ו-precision
   לבדו לא אומר עליו כלום. בקש את **ההתפלגות המלאה** של גודל התנועה בהינתן סיגנל, לא רק אחוז.
3. **שרידוּת ה-75% בלייב** — שהמודל עבר purged CV + walk-forward + DSR, בלי leakage. [מסמך 04, 08]

אם `E[|move| | hit]` >> breakeven עם margin, ה-IV לא מנופח מאירוע, וה-75% שורד OOS — יש אסטרטגיה.

---

## מדריך קריאה (לפי סדר)

| מסמך | מה תמצא | למי |
|---|---|---|
| **03 · core-profitability-model** | הליבה: ה-identity, פירוק ה-EV, VRP, דוגמאות עובדות | קרא ראשון |
| **04 · signal-to-edge** | precision≠win-rate, מה לבקש מה-ML, meta-labeling, Kelly | חובה |
| **05 · volatility-events-execution** | VRP, IV crush, Regime A/B, 0DTE, חיכוך | חובה |
| **02 · strategy-landscape** | straddle מול strangle/backspread/short-premium/gamma-scalp | להקשר |
| **06 · instruments** | מיפוי זהב/נאסד״ק, מס §1256, עונתיות, מסגרת הכללה | מעשי |
| **07 · backtesting** | נתונים, מלכודות, purged CV, loop | לפני אימות |
| **08 · risks-and-playbook** | adversarial, עדות אקדמית, ניהול תיק, playbook חי | לפני הון |
| **sources.md** | ביבליוגרפיה מאוחדת (כל המקורות) | אסמכתאות |
| **../workflows/research-workflow.md** | המנוע: פירוק, סוכנים, שערי G1–G8, runbook | להרצה מחדש |

---

## הכלי — `tools/straddle_ev.py`

מנוע EV/breakeven/Kelly פרמטרי (stdlib בלבד, ללא תלויות). דוגמאות:

```bash
# התנועה הגלומה ומחיר ה-straddle מ-IV (זהב, 120 דק'):
python tools/straddle_ev.py implied --S 4490 --iv 0.245 --minutes 120 --basis gold24x5

# EV מ-precision + תנועה מותנית:
python tools/straddle_ev.py ev --premium 16.3 --cost 0.4 -p 0.75 --mu-hit 35 --mu-miss 8

# הרף: כמה גדולה צריכה להיות התנועה ב-hit כדי לא להפסיד:
python tools/straddle_ev.py required --premium 16.3 --cost 0.4 -p 0.75 --mu-miss 8

# Monte-Carlo עם התפלגות מלאה + Kelly:
python tools/straddle_ev.py mc --premium 16.3 --cost 0.4 -p 0.75 \
    --hit-mean 35 --hit-cv 0.8 --miss-mean 8 --kelly
```

---

## דוגמה מספרית (זהב, להמחשה)
ב-`S=$4,490`, `GVZ≈24.5`, 120 דק': התנועה הגלומה ≈ $16–20, וסף $25 ≈ **1.25–1.6σ**. אם ה-ML team
יראה ש-`E[|move| | hit] ≈ $35` (מעל הרף ~$19.6), ה-EV חיובי (~+$11.5/straddle) — **בתנאי** שאתה
נכנס ב-IV לא־מנופח (Regime B), ושה-75% שורד OOS. כל המספרים ניתנים לשחזור עם הכלי.

---

## אזהרה
זה חומר מחקר וחינוך, **לא ייעוץ השקעות**. מסחר באופציות כרוך בסיכון להפסד מלא של הפרמיה (ויותר
במבני שורט). רמות השוק מתוארכות ליוני 2026 — רענן מהשרשרת החיה לפני כל החלטה.
