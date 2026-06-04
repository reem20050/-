# 02 · נוף האסטרטגיות — איפה ה-Long Straddle יושב ומתי משהו אחר עדיף

> סיגנל מגניטודה (כיוון לא ידוע) הוא הימור על תנודתיות. ה-long straddle הוא ברירת המחדל, אבל
> יש משפחה שלמה של מבנים — וחלקם עדיפים בתנאים מסוימים. הכלל: **הבחירה תלויה בגודל התנועה
> הצפוי מול עלות האופציה, ברמת הביטחון, והאם ה-IV זול או יקר.**

---

## 1. טבלת ההשוואה הראשית

| מבנה | עלות | סיכון מקס' | הכי טוב כש... |
|---|---|---|---|
| **Long straddle** (call+put ATM) | גבוהה | ה-debit | IV זול; תנועה צפויה אבל גודל לא ודאי; רוצים breakeven צר |
| **Long strangle** (OTM call+put) | נמוכה יותר | ה-debit | תנועה צפויה **גדולה** + IV בינוני; שימור הון |
| **Long guts** (ITM call+put) | גבוהה ברוטו (אבל intrinsic מוחזר) | extrinsic בלבד | נזילות OTM גרועה; מעדיפים להחזיק intrinsic |
| **Call/Put backspread** (short 1 ATM, long 2 OTM) | נמוכה/אפס/credit | חסום (בשורט strike) | תנועה חזקה בכיוון **אחד**; convex; lean כיווני |
| **Gamma scalping** (straddle + delta-hedge) | פרמיה + עלויות חיתוך | ה-debit, נשחק ע"י theta | RV צפוי >> IV; סיגנל יורה הרבה; נכס מהיר |
| **Double calendar** (short front, long back) | בינונית | ה-debit | term structure תלול; המהלך **אחרי** פקיעת ה-front |
| **Short straddle** | credit | תיאורטית בלתי מוגבל | המודל מנבא **אין** תנועה בביטחון; IV יקר |
| **Iron condor / butterfly** (short-vol מוגדר־סיכון) | credit | רוחב הכנפיים − פרמיה | מנבא טווח; IV rank גבוה; רוצים סיכון חסום |

> **debit spread (vertical) הוא לא long-vol** — ה-leg הקצר מקזז את ה-vega/gamma. אל תחליף בו straddle.

---

## 2. שני הניואנסים שהכי משנים

### א. Short-premium עשוי להיות ה-edge הגדול יותר
אם המחלקה ה**שלילית** של המודל ("אין תנועה") גם מדויקת ~75%, אז **מכירת** פרמיה (short straddle /
iron condor / butterfly) קוצרת את ה-VRP — שהוא רוח גבית מבנית (IV>RV ב-~78–85% מהזמן). זה עשוי
להיות רווחי יותר מהצד הארוך, כי אתה הופך להיות מוכר הביטוח במקום הקונה.
⚠️ אבל: short premium = סיכון זנב שמאלי. עסקה גדולה אחת שגויה מוחקת הרבה מנצחות → **חובה**
מבנה מוגדר־סיכון (iron condor על short strangle עירום) ו-sizing קטן.

### ב. Calendars הם short-gamma בטווח הקצר
long calendar רגיל הוא **short gamma** בטווח הקרוב ו-long vega — מרוויח מ**עליית IV בלי מהלך גדול**,
ההפך ממה שסיגנל "תנועה גדולה" צריך. ה-leg הקצר נהרס אם המהלך מגיע לפני פקיעת ה-front. רלוונטי
רק אם המהלך צפוי **אחרי** פקיעת ה-front + ציפייה לקפיצת IV.

---

## 3. Gamma scalping — מתי לקצור RV במקום פשוט להחזיק

מחזיקים straddle (long gamma) ומגדרים delta ל-0 שוב ושוב, וממירים את הקמירות לתזרים "קנה־נמוך/מכור־גבוה".

**ה-identity:** רווח לכל צעד ≈ `½·Γ·(dS)² − Θ·dt`. מצטבר: `PnL ≈ ½·Vega·(σ²_realized − σ²_implied)·T`.
כלומר **רווחי אם ורק אם RV > IV** — בדיוק כמו ה-straddle, אבל מחלץ variance ללא תלות בכיוון.

| מתי scalping **עדיף** על hold | מתי **hold** עדיף על scalping |
|---|---|
| שוק גלי / mean-reverting (כל תנודה מוסיפה רווח) | קפיצה כיוונית גדולה אחת (ה-holder לוקח את כל ה-intrinsic) |
| היפוכי כיוון מרובים בחלון | חלון קצר מאוד (60–120 דק', 2–4 hedges בלבד) |
| תוכנית רציפה על הרבה סיגנלים (LLN) | סיגנל בודד — ה-scalp מוסיף חיכוך בלי מספיק צעדים |

> **לסיגנל בינארי בודד לחלון של שעתיים — hold-and-exit עדיף** (המהלך נתפס מיד בערך ה-straddle).
> scalping מצדיק את עצמו רק כתוכנית רציפה עם עלויות חיתוך נמוכות (הקשר market-maker).
> תדירות hedge אופטימלית: רצועת Whalley–Wilmott `w = [3·k·S·Γ²/(2a)]^(1/3)`.

---

## 4. סולם מכשירי התנודתיות (retail → institutional)

לסיגנל מגניטודה קצר־טווח על נכס **ספציפי**, ה-straddle הקצר על אותו נכס הוא בד"כ המכשיר
**הישיר ביותר**. מוצרי vol סחירים (VIX/GVZ) **לא מתאימים** בגלל 3 אי־התאמות בו־זמנית:
1. **נכס:** VIX=IV של S&P, GVZ=IV של GLD — לא הנכס שלך.
2. **אופק:** הם מודדים IV ל-30 יום, לא מהלך של 60–120 דקות (פי 200–400 קצר יותר).
3. **roll drag:** VIX futures ב-contango ~80% מהזמן → 3–7% נשיכה חודשית.

הסולם:
```
Long straddle  →  Strangle  →  Delta-hedged straddle (gamma scalp)  →  Corridor var swap  →  Variance swap
   הכי פשוט         זול יותר         מקרב variance capture              institutional        הביטוי הנקי (OTC, ISDA, $1M+)
```
variance swap הוא הביטוי הטהור ל-long-RV (תשלום `N·(σ²_realized − K_var)`), אבל OTC/מוסדי בלבד.
**המלצה לריטייל לחלון שעתיים: short-dated ATM straddle/strangle על הנכס עצמו.**

---

## 5. מטריצת החלטה — מאפיין הסיגנל → מבנה

| מאפיין | מבנה מומלץ |
|---|---|
| "תנועה" + IV זול + כיוון לא ידוע | **Long straddle** |
| "תנועה" + IV זול + מהלך צפוי גדול מאוד | Long strangle |
| "תנועה" + נזילות OTM גרועה | Long guts |
| "תנועה" + lean כיווני חלש | Call/Put backspread |
| סיגנל יורה הרבה + RV>>IV | Gamma scalping (תוכנית רציפה) |
| "אין תנועה" + IV rank גבוה | Short straddle / Iron condor (מוגדר־סיכון) |
| אופק ימים-שבועות + מוסדי | Variance swap |

### קישורים
- מסמך 03 — למה ה-straddle מתומחר כמו E\|move\| (הבסיס לכל הבחירות).
- מסמך 05 — IV crush ובחירת expiry, שמשפיעים על איזה מבנה ישרוד.
- מסמך 06 — אילו מבנים זמינים בפועל בכל מכשיר.
