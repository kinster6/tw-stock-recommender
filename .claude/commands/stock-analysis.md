Run data-driven Taiwan stock technical analysis for one or more stock symbols and provide a weekly position-sizing recommendation.

## Steps

1. Run the analysis script with the provided symbols:
   ```
   python3 tech_analysis.py $ARGUMENTS
   ```

2. Present the results with these sections clearly explained:

   **技術指標快照** — Current KD/RSI/MACD/MA values.

   **三大法人** — Institutional buy/sell over last 5 trading days (外資/投信/合計), including consecutive-day streaks.

   **歷史回測表格** — The core data-driven section:
   - Each row is a technical condition evaluated against the past 6 months of history for this specific stock
   - **超額邊際** = (condition's up_rate − down_rate) minus the baseline edge (the natural win rate if you do nothing). Positive = historically bullish for THIS stock; negative = historically bearish
   - ★ = condition is active today AND scored (one per indicator group to avoid double-counting)
   - ✓ = active today but outcompeted by a stronger signal in the same group
   - Non-active rows show what patterns to watch for

3. Write a 3–4 sentence analyst commentary in Traditional Chinese covering:
   - What the most significant active signals (★) are and why they matter for this stock specifically
   - Key non-active signals with high |超額邊際| that the user should watch for (potential triggers)
   - The institutional picture and whether it aligns or diverges from the technical signal
   - Overall risk/reward and how aggressively the user might consider sizing their position this week

4. If multiple stocks are analyzed, end with a comparison summary table:
   `股票 | 收盤價 | 技術分 | 籌碼分 | 合計 | 建議`

## Scoring logic (for reference)

- **技術分數**: For each ★ condition, contribution = excess_edge × confidence (confidence saturates at ~20 historical samples). One winner per indicator group (KD/MACD/RSI/MA5/MA20/MA60/MA200/Volume/Compound).
- **籌碼分數**: Fixed scoring for institutional trends (外資/投信 consecutive days, directional alignment).
- **合計**: tech_score + inst_score × 0.12
- Thresholds:
  - ≥ +0.60 → 強力加碼 🚀（強勢多頭信號）
  - ≥ +0.25 → 加碼 ↑（技術面偏多）
  - > −0.25 且 < +0.25 → 持平 →（信號混合）
  - ≤ −0.25 → 減碼 ↓（技術面偏空）
  - ≤ −0.60 → 強力減碼 ⚠（強勢空頭信號）

## Recommendation interpretation

The labels are **position-sizing guidance**, not binary buy/sell:

| 建議 | 倉位操作 |
|------|---------|
| 強力加碼 | 增持至 75–100% |
| 加碼 | 增持約 25% |
| 持平 | 維持現有倉位 |
| 減碼 | 減持約 25% |
| 強力減碼 | 大幅減持至 0–25% |

## Notes
- Stock symbols are Taiwan exchange codes (e.g., 2330=台積電, 0050=台灣50 ETF)
- The script automatically tries TWSE (.TW) then OTC (.TWO)
- Results are stock-specific: the same pattern can be bullish for one stock and bearish for another
- These are technical signals only — always consider fundamental factors and personal risk tolerance
- If a symbol errors out, report it and continue with the rest
