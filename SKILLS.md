# Claude Code Skills

This repository includes a custom Claude Code slash command for Taiwan stock technical analysis.

## `/stock-analysis` — Taiwan Stock Technical Analysis

Run data-driven technical analysis on one or more Taiwan Stock Exchange (TWSE/TPEx) listed stocks and get a weekly position-sizing recommendation.

### Usage

In Claude Code, type:

```
/stock-analysis 2330 2344 2408
```

You can pass any number of Taiwan stock codes (e.g. `2330` for TSMC, `2344` for Winbond, `0050` for Taiwan 50 ETF).

### What it does

For each stock, the skill:

1. **Fetches price data** — 400 days of unadjusted OHLCV data via yfinance (enough for MA200)
2. **Calculates technical indicators**:
   - KD (9-period RSV with Taiwan-standard 1/3 EMA smoothing, initial K=D=50)
   - RSI(14) using SMA-based (Cutler's) method — matches Taiwan stock apps
   - MACD(12,26,9) with EWM adjust=False
   - MA 5/20/60/200/240 (simple moving averages)
   - BIAS 乖離率 for 5/20/60 periods
3. **Backtests 50+ technical conditions** against the past 6 months of this stock's own history, computing each condition's historical up/down rate and excess edge over baseline
4. **Fetches institutional data (三大法人)** — foreign investors (外資), investment trusts (投信), and dealers (自營商) from TWSE/TPEx official APIs
5. **Fetches global market indicators** — CBOE VIX and Taiwan Buffett Indicator
6. **Scores and recommends** a position-sizing action for the coming week

### Output sections

| Section | Description |
|---------|-------------|
| 技術指標快照 | Current snapshot of KD, RSI, MACD, MA, and BIAS values |
| 總體市場指標 | VIX fear index + Taiwan Buffett Indicator |
| 三大法人 | Institutional net buy/sell over 5 days with consecutive-day streaks |
| 歷史回測 | Every technical condition ranked by historical excess edge (★ = active & scored today) |
| 建議 | Position-sizing recommendation from 強力減碼 ⚠ to 強力加碼 🚀 |

### Recommendation scale

| 建議 | English | Position action |
|------|---------|----------------|
| 強力加碼 🚀 | Strong Add | Increase to 75–100% |
| 加碼 ↑ | Add | Increase ~25% |
| 持平 → | Hold | Maintain current position |
| 減碼 ↓ | Reduce | Decrease ~25% |
| 強力減碼 ⚠ | Strong Reduce | Decrease to 0–25% |

### Scoring logic

- **Tech score**: For each active ★ condition, `contribution = excess_edge × confidence` (confidence saturates at 20 samples). One winner per indicator group (KD / MACD / RSI / MA5 / MA20 / MA60 / MA200 / Volume / Compound) to prevent double-counting.
- **Institutional score**: Fixed points for consecutive foreign/trust buy or sell streaks and directional alignment.
- **Combined**: `tech_score + inst_score × 0.12`

### Installation

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. The `.claude/commands/stock-analysis.md` file is picked up automatically by Claude Code

```bash
git clone https://github.com/your-username/stock-recommender.git
cd stock-recommender
pip install -r requirements.txt
```

Then open the folder in Claude Code and type `/stock-analysis 2330`.

### Notes

- Stock codes are Taiwan exchange codes (TWSE or TPEx)
- The script automatically tries `.TW` (TWSE) then `.TWO` (TPEx)
- All signals are stock-specific — the same pattern can be bullish for one stock and bearish for another
- These are technical signals only; always consider fundamentals and personal risk tolerance
- Disclaimer: Not financial advice
