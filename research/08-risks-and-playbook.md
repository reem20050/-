# 08 · סיכונים, עדות אקדמית, ניהול תיק, ו-Playbook חי

> המסמך המאזן: למה רוב קוני ה-straddle מפסידים, מה האקדמיה באמת מראה, איך מנהלים סיכון ברמת תיק,
> ואיך נראה playbook ביצוע אמיתי. קרא את זה לפני שאתה מסכן שקל.

---

## 1. השורה התחתונה הכנה (Devil's Advocate)

קוני long straddle נלחמים ברוח גבית מבנית מהיום הראשון:
- IV עולה על RV ב-**~85%** מהזמן; ה-VRP ~**3–5 נק'** שנתיות (Carr-Wu).
- מחקר tastytrade על SPY straddles (5–10 DTE): **חציון P&L שלילי** ו-win-rate מתחת ל-50%, אפילו
  בסביבת IV rank נמוך.
- straddle **מתומחר הוגן** מפסיד ב-~58% מהפעמים (B-S).

**הרף הכן לסיגנל שלך — שלושה תנאים בו־זמנית:**
1. הסיגנל מנבא **גודל** מהלך, לא רק כיוון/התרחשות. מהלך של 4% כשה-straddle מתמחר 8% = הפסד.
2. ה-IV rank בכניסה **באמת נמוך** (Regime B). אפילו בחירת IV rank<25 לא הצילה את ה-SPY במחקר —
   ה-edge חייב להיות גדול מספיק כדי לגבור.
3. ה-25% miss **שרידים** — 1 מ-4 הוא הפסד כמעט מלא; 3 רצופים יכולים למחוק חשבון ממונף. Kelly חלקי קריטי.

---

## 2. מה האקדמיה באמת מראה (case studies)

| מחקר | ממצא | משמעות |
|---|---|---|
| **Coval & Shumway (2001)** | zero-beta ATM straddles על S&P מפסידים **~3%/שבוע** | להיות long-vol לא־מותנה = יקר מבנית |
| **Bakshi & Kapadia (2003)** | delta-hedged long calls מפסידים **−3.31%/מחזור**; גרוע יותר בתנודתיות גבוהה | ה-VRP לא ניתן לגידור |
| **Carr & Wu (2009)** | VRP שלילי מובהק לאינדקסים; **קרוב ל-0/חיובי במניות בודדות** | מניות בודדות מטרה טובה יותר מ-SPX |
| **Goyal & Saretto (2009)** ⭐ | קניית straddles כש-HV>>IV: long-short ~**22.7%/חודש** ברוטו → **~3.9%/חודש** אחרי עלויות | **edge מותנה־תחזית עובד** — בחתך־רוחב, על מניות |

**הסינתזה הכנה:** Goyal-Saretto הוא העדות האקדמית הקרובה ביותר ל"קנה straddle כשהתחזית שלך > IV" —
וזה **עובד**, אבל עם 3 הסתייגויות: (א) עלויות אוכלות את רוב האלפא; (ב) זה אפקט **חתך־רוחב** (אילו
נכסים), לא market-timing; (ג) ה-VRP חייב להיגבר עליו עם margin — מהלך שרק שולית מעל IV יפסיד.
**מסקנה:** edge מגניטודה אמיתי ומכויל *יכול* לגבור על ה-VRP, בעיקר על **נכסים בודדים** (לא אינדקסים),
עם ניהול עלויות אגרסיבי. כ-market-timing על אינדקס — הספרות לא תומכת.

---

## 3. האם ה-75% ישרוד לייב? (validity)

ה-75% precision שווה משהו רק אם הוא לא artifact. הסיכונים, מסודרים לפי חומרה:
1. **Look-ahead / leakage (החמור ביותר):** אם feature כלשהו משתמש בנתון מתוך חלון ה-label [t,t+N] →
   ה-precision אשלייתי. דרוש audit של timestamps שורה־שורה.
2. **train/test contamination:** k-fold רגיל דולף. אם השתמשו ב-`KFold` של sklearn — המדדים חסרי משמעות.
   דרוש **purged + embargoed CV**.
3. **non-stationarity / regime change:** בדוק שה-75% מחזיק על מספר רגימות (לפני/אחרי 2022, vol גבוה/נמוך).
4. **multiple testing:** כמה תצורות נוסו לפני שהגיעו ל-75%? דרוש **Deflated Sharpe**.
5. **בחירת סף X על כל הדאטה / נרמול בכל המדגם:** מדליף עתיד.
6. **פער backtest→live:** latency, spreads, market impact — סיגנל ש"יורה" 10ms אחרי ש-HFT תמחר = אפס.
7. **alpha decay:** edge קצר־טווח דועך תוך חודשים; crowding מאיץ.

**7 שאלות ל-ML team:** (1) audit timestamps? (2) purged CV + embargo? (3) כמה תצורות נוסו + DSR?
(4) precision פר רגים? (5) הסף נבחר על train בלבד? (6) walk-forward עם אימון חודשי? (7) paper-trading
עם latency ו-spreads אמיתיים — מה ה-Sharpe נטו?

---

## 4. ניהול סיכון ברמת תיק

**מתמטיקה:**
- **Risk of ruin:** `RoR ≈ ((1−edge)/(1+edge))^N`, כש-`N = הון/סיכון-לעסקה`. ב-1% לעסקה (N=100) → RoR≈0.
  ב-5% (N=20) → עולה חדות. **חצי הסיכון ≈ ריבוע ההגנה.**
- **רצף הפסדים צפוי:** `E[max streak] ≈ ln(trades)/ln(1/q)`. ב-q=0.25, 200 עסקאות → ~4 רצופים שגרתי.
  4 רצופים ב-2%/עסקה = ~8% drawdown; ב-5% = ~20%.
- **full Kelly → ~33% סיכוי ל-drawdown של 50%.** half-Kelly משמר ~75% מהצמיחה עם חצי drawdown.

**סיכון רצף (הנקודה העיוורת):** סיגנלים מקובצים (כמה straddles באותו חלון אירוע) → הפסדים מתואמים,
שיעור ההפסד האפקטיבי גבוה מ-25%, וה-drawdown חמור פי 1.5–2 ממתמטיקת IID. השתמש ב-**block bootstrap**
בסימולציה.

**checklist בקרת סיכון:**
- [ ] סיכון פרמיה לעסקה ≤ **1–2%** מה-NAV (הפרמיה המלאה, לא notional)
- [ ] סך פרמיה פרוסה ≤ **10–15%** מה-NAV בו־זמנית
- [ ] מקס' פוזיציות במקביל: 5–8; הפחת אם מקובצות לאותו אירוע
- [ ] תקרת נכס/סקטור בודד ≤ 30% מהפרמיה הפרוסה
- [ ] תקציב theta יומי מצרפי ≤ 0.08–0.10% מה-NAV/יום
- [ ] **circuit breaker יומי:** הפסד MTM > 2–3% מה-NAV → עצור כניסות חדשות היום
- [ ] **circuit breaker drawdown:** −10% מהשיא → חצי sizing; −15% → עצור עד בדיקה
- [ ] תקציב slippage: הנח ≥3–5% מהפרמיה; אם ה-EV לא שורד — דלג
- [ ] תיאום: אם ρ בין נכסים פתוחים > 0.5 → התייחס כפוזיציה אחת ל-sizing (`N_eff ≈ N/(1+(N−1)ρ)`)
- [ ] baseline = **¼ Kelly**, לא full

**סימולציית MC לפני לייב:** block bootstrap (לשמר clustering), הזרק רצפי הפסד, פלט: התפלגות max
drawdown (חציון/95/99), P(ruin), Calmar. **קריטריון קבלה:** drawdown ב-99% < 25% NAV, P(ruin)<1%, Calmar>1.

---

## 5. Playbook ביצוע חי

### כניסה
1. סיגנל יורה → אבחן Regime: בדוק IV%ile ברגע הסיגנל. אם מנופח מאירוע (>65) — **דלג** או הקטן.
2. בחר מכשיר נזיל + מעמד §1256 (NDX/GC/NQ עדיף; מסמך 06).
3. בחר expiry: **1–2 DTE** לחלון שעתיים (לא 0DTE אחר הצהריים; מסמך 05).
4. שלח **combo order (straddle כיחידה) ב-mid**, לא legging, לא market. אם לא מתמלא ב-15–30ש' → תקן
   ל-mid+10% מה-spread; ב-60ש' → בטל ודלג.
5. גודל לפי ¼ Kelly, ≤1–2% NAV.

### יציאה
6. **יציאה מבוססת־זמן:** סגור אחרי N דקות (combo).
7. **יציאה על המהלך:** אם המהלך קרה — סגור ולכוד את ה-gamma; אל תחזיק לפקיעה (theta).
8. **stop:** הפסד של ~1× הפרמיה או circuit breaker יומי → סגור מיד.

### אוטומציה
- **ברוקרים/APIs:** IBKR (TWS API/ib_insync — combo `BAG`, FOPs, paper port 7497), tastytrade
  (multi-leg, futures options, sandbox), Tradier (multi-leg, equity only), TradeStation (הכל).
- **pipeline:** chain cache (רענון 30ש') → על סיגנל שלח combo limit ב-mid → תזמן יציאה ל-N דק' →
  kill-switch בודק daily-loss/drawdown לפני כל שליחה.
- **סיכונים תפעוליים:** API outage (IB Gateway + reconnect), partial fill (combo מונע legging),
  spread blow-out (סף spread לפני שליחה — דלג אם רחב), נזילות off-hours (הגבל לסשנים נזילים),
  chain cache ישן (>60ש' → רענן לפני order).
- **חובה:** 30–60 יום **paper-trading** באותו code path; הוסף ל-backtest slippage של 0.5–1× spread
  ו-latency 100–200ms; אם עדיין +EV — robust מותנה.

---

## 6. מטריצת הסיכונים המסכמת

| סיכון | חומרה | מיטיגציה |
|---|---|---|
| IV crush (כניסה ב-Regime A) | גבוהה | אבחון IV%ile; דלג סביב אירועים מתוזמנים |
| VRP מבני | גבוהה | edge מותנה גדול; שקול short-premium על המחלקה השלילית |
| precision אשלייתי (leakage/overfit) | גבוהה | purged CV, DSR, walk-forward, paper-trading |
| חיכוך ביצוע | בינונית | SPX/NDX, combo ב-mid, הימנע מפתיחה/סגירה |
| רצף הפסדים / ruin | בינונית-גבוהה | ¼ Kelly, ≤1–2%/עסקה, circuit breakers |
| clustering/קורלציה | בינונית | `N_eff`, תקרות סקטור, block-bootstrap MC |
| alpha decay | בינונית | ניטור רציף, walk-forward מתמשך |
| תפעולי (API/fills) | נמוכה-בינונית | combo orders, kill-switch, paper-trading |

### קישורים
- מסמך 03/04 — EV, מה לבקש מה-ML team, Kelly.
- מסמך 05 — Regime A/B, expiry, חיכוך.
- מסמך 07 — backtest שמזין את ה-MC ואת ה-EV.
- `workflows/research-workflow.md` — שערי G1–G8 שמכריחים את כל זה לפני הון.
