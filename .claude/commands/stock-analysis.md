Comprehensive Taiwan stock analysis. Orchestrates available sub-analyses and combines them into a unified recommendation.

## Available sub-commands

| Sub-command | What it does |
|-------------|-------------|
| `/tech-analysis` | Technical indicators + institutional flow + market regime → position-sizing signal |

## Steps

1. Parse `$ARGUMENTS` to get stock symbol(s).

2. Run `/tech-analysis $ARGUMENTS` and present its full output.

3. If only one sub-analysis is available (current state), present the tech-analysis results directly and note at the end:

   > **分析模組**: 技術面 ✅  基本面 🔜  消息面 🔜

4. When multiple sub-analyses are available in the future, synthesize them into a final verdict table:
   `股票 | 技術面 | 基本面 | 消息面 | 綜合建議`

## Notes
- Stock codes are Taiwan exchange codes (e.g. 2330=台積電, 0050=台灣50 ETF)
- This command is the entry point; it delegates to sub-commands for each analysis type
- Not financial advice
