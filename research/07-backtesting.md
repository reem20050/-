# 07 · מתודולוגיית Backtest ואימות — איך לדעת אם ה-Edge אמיתי

> backtest שגוי של אסטרטגיית אופציות תוך־יומית הוא הדרך הקלה ביותר ל"גלות" edge מדומה. המסמך
> הזה נותן את הנתונים, המלכודות, וה-loop הנכון.

---

## 1. נתונים — צריך quotes תוך־יומיים עם bid/ask ו-greeks

לחלון של 60–120 דק' חייבים נתוני דקה (לא EOD), עם bid/ask אמיתי (לא רק mid) ו-IV/greeks.

| ספק | תוך־יומי? | greeks/IV? | הערות |
|---|---|---|---|
| **ORATS** | כן — דקה מאוג' 2020 | כן — מלא + "smoothed value" לסימון quotes תקועים | בחירה ראשית למניות/ETF |
| **CBOE DataShop / LiveVol** | כן — סיכומי דקה + NBBO; tick | כן (תוסף Calcs) | מקור CBOE סמכותי, מ-2011 |
| **SpiderRock** | כן — 5 דק'; 1 דק' ATM vol | כן — NBBO IV + surface | מarks ל-T+1M/T+10M לסימולציית fill |
| **Databento (OPRA)** | כן — tick/L1 NBBO, ננו | לא — quotes גולמי | הכי טוב ל-NBBO; greeks עצמית |
| **Polygon.io** | כן — tick + aggregates מ-2021 | כן | ארגונומיה טובה למפתחים |
| **OptionMetrics IvyDB Intraday** | חלקי — 3 snapshots/יום | כן | **לא מספיק** לכניסות בזמן שרירותי |

**המלצה:** ORATS 1-min או CBOE DataShop 1-min לחלון שעתיים; Databento כ-fallback ל-quotes גולמי.

---

## 2. המלכודות הספציפיות לאופציות (כל אחת הופכת edge מדומה לאמיתי)

1. **fills ב-mid (קריטי):** הנחת mid מנפחת P&L. קנה ב-**ask**, מכור ב-**bid**. אמפירית, slippage
   ~75% מחצי־ה-spread לאופציה בודדת, ~56% ל-straddle דו־רגלי.
2. **quotes תקועים/רחבים בפתיחה/סגירה:** market makers מרחיבים. דגום ~14 דק' לפני סגירה; ודא
   quote חי (bid>0, bid<ask, גיל<bar).
3. **look-ahead/leakage:** הסיגנל ב-bar T משתמש רק בנתונים לפני סגירת T. greeks בכניסה מ-bar T,
   לא T+1. זו הסיבה מס' 1 ל-edge מדומה ב-ML פיננסי.
4. **survivorship:** universe point-in-time; כלול נכסים שנמחקו/מוזגו עד תאריך אחרון.
5. **בחירת expiry:** הימנע מ-0DTE אלא אם מכוון; weekly 4–7 DTE כנקודת התחלה.
6. **theta על ההחזקה:** השתמש ב-bid/ask של bar היציאה האמיתי, לא אקסטרפולציה מ-greeks הכניסה.
7. **שווקים נעולים/חצויים בדאטה:** סנן bid>ask או bid=0 לפני הריצה.

---

## 3. תקפות סטטיסטית (López de Prado) — נגד overfitting

- **Purged + Embargoed CV:** k-fold רגיל **דולף** בסדרות זמן (תצפיות סמוכות חולקות תהליך תיוג).
  *Purge* — הסר אימון שה-label שלו חופף ל-test. *Embargo* — פער חוצץ אחרי כל test fold. (`mlfinlab`).
- **Walk-forward:** אמן שנים 1–3, בדוק שנה 4, התקדם ב-6 חודשים, חזור.
- **Deflated Sharpe Ratio (DSR):** אם בדקת K תצורות, ה-Sharpe המקסימלי מוטה כלפי מעלה. דווח DSR,
  לא Sharpe גולמי (Bailey & López de Prado 2014).
- **מספר סיגנלים:** כוון ל-**≥200 עסקאות OOS** עצמאיות; bootstrap לרווח־סמך על ה-P&L.

> שילוב עם validity של המודל (מסמך 04): אם ה-ML team השתמש ב-`KFold` רגיל של sklearn — מדדי
> ה-CV חסרי משמעות. דרוש purged CV + walk-forward + DSR לפני שמאמינים ל-75%.

---

## 4. ה-Backtest Loop הנכון (pseudocode)

```python
# options_1min: indexed by (symbol, expiry, strike, type, ts) -> bid, ask, delta, gamma, vega, theta, iv
# signals:      [(ts, underlying)]
results = []
for sig_ts, sym in signals:
    entry_ts = next_bar(sig_ts, "1min")
    expiry   = select_expiry(sym, entry_ts, min_dte=4, max_dte=7)   # לא 0DTE כברירת מחדל
    spot     = get_spot(sym, entry_ts)
    strike   = nearest_strike(sym, expiry, spot, entry_ts)

    call_e = options_1min.loc[(sym, expiry, strike, "C", entry_ts)]
    put_e  = options_1min.loc[(sym, expiry, strike, "P", entry_ts)]
    if call_e.bid<=0 or put_e.bid<=0:           continue   # quote תקוע
    if call_e.ask<=call_e.bid or put_e.ask<=put_e.bid: continue  # נעול/חצוי

    entry_debit = call_e.ask + put_e.ask        # קנה ב-ASK (שמרני)

    N = 90                                       # דקות; כוון רק OOS
    exit_ts = clamp_to_session(entry_ts + minutes(N), sym)   # לא אחרי 15:55
    call_x = options_1min.loc[(sym, expiry, strike, "C", exit_ts)]
    put_x  = options_1min.loc[(sym, expiry, strike, "P", exit_ts)]
    exit_credit = call_x.bid + put_x.bid         # מכור ב-BID

    commission = 2*2*0.65                         # 2 legs × 2 כיוונים
    net_pnl = (exit_credit - entry_debit)*100 - commission   # multiplier 100
    results.append({entry_ts, strike, expiry, entry_debit, exit_credit, net_pnl,
                    "entry_iv": (call_e.iv+put_e.iv)/2})

# הערך רק על fold OOS: win-rate, mean net PnL, DSR, max drawdown, מספר עסקאות
```

**אינווריאנטים:** כניסה תמיד ב-ask, יציאה תמיד ב-bid; ולידציית quote לכל כניסה; N ו-expiry קבועים
לפני ה-OOS.

---

## 5. גשר ל-EV התיאורטי
ה-backtest צריך לאשש את מודל ה-EV (מסמך 03). השווה: `mean net PnL` מה-backtest מול
`straddle_ev.py ev` עם ה-`E[|move| | hit]` שחושב מאותו דאטה. פער גדול = באג ב-backtest או הנחה
שגויה. ה-`entry_iv` שנרשם מאפשר לאמת אם נכנסת ב-Regime A או B (מסמך 05).

### קישורים
- מסמך 04 — validity של המודל, purged CV, מה לבקש מה-ML team.
- מסמך 05 — בחירת expiry, חיכוך, Regime A/B (entry_iv).
- מסמך 08 — מ-backtest ל-paper-trading ל-live.
