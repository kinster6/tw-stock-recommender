Run data-driven technical analysis on one or more Taiwan stock symbols and output a weekly position-sizing recommendation.

## Steps

1. Run the analysis script:
   ```
   python3 tech_analysis.py $ARGUMENTS
   ```

2. Present the raw output with these sections explained:

   **技術指標快照** — Current KD/RSI/MACD/MA/BIAS values.

   **總體市場指標** — VIX, Taiwan Buffett Indicator, TWII vs MA200 regime (強多頭/多頭/中性/空頭) and its score adjustment.

   **三大法人** — Foreign investors (外資) and investment trust (投信) net buy/sell over last 5 days, with consecutive-day streaks and 10-day cumulative.

   **歷史回測表格** — The core data-driven section:
   - Each row = one technical condition evaluated against the past 6 months of THIS stock's history
   - **超額邊際** = (condition's up_rate − down_rate) − baseline. Positive = historically bullish for this stock; negative = bearish
   - ★ = active today AND scored (one winner per indicator group)
   - ✓ = active today but outcompeted in the same group
   - Non-active rows show patterns to watch for

3. Write a 3–4 sentence analyst commentary in Traditional Chinese:
   - Most significant ★ signals and why they matter for this stock specifically
   - High |超額邊際| non-active signals worth watching (potential triggers)
   - Whether institutional flow aligns or diverges from the technical picture
   - Overall risk/reward and position-sizing suggestion for the coming week

4. If multiple stocks: end with a comparison table
   `股票 | 公司名 | 收盤價 | 技術分 | 籌碼分 | 市場趨勢 | 合計 | 建議`

## Scoring

- **Tech score**: active ★ conditions, `weight = excess_edge × confidence` (confidence saturates ~20 samples). One winner per group (KD / MACD / RSI / MA5 / MA20 / MA60 / MA200 / Volume / Compound).
- **Institutional score**: fixed points for consecutive foreign/trust streaks and directional alignment.
- **Market regime bonus**: +0.25 (強多頭) / +0.15 (多頭) / 0 (中性) / -0.15 (空頭) based on TWII vs MA200.
- **Combined** = tech + inst × 0.12 + regime_bonus

## Recommendation thresholds

| Combined score | Regime | Recommendation |
|---------------|--------|---------------|
| ≥ +0.60 | any | 強力加碼 🚀 |
| ≥ +0.25 | any | 加碼 ↑ |
| ≤ −0.40 | 強多頭 | 減碼 ↓ |
| ≤ −0.25 | others | 減碼 ↓ |
| ≤ −0.80 | 強多頭 | 強力減碼 ⚠ |
| ≤ −0.60 | others | 強力減碼 ⚠ |
| otherwise | — | 持平 → |

## Notes
- Stock codes are Taiwan exchange codes (e.g. 2330=台積電, 0050=台灣50)
- Script auto-tries `.TW` (TWSE) then `.TWO` (TPEx)
- Signals are stock-specific — the same pattern can be bullish for one stock and bearish for another
- Not financial advice; always consider fundamentals and personal risk tolerance
