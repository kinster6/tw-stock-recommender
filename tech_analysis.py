#!/usr/bin/env python3
"""
Taiwan Stock Technical Analysis — Data-Driven Edition
Instead of fixed if/else scoring, every technical signal is evaluated by its
actual historical hit rate over the past 6 months for the specific stock.
"""

from __future__ import annotations
import sys
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import yfinance as yf
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from ta.momentum import StochasticOscillator, RSIIndicator
from ta.trend import MACD, SMAIndicator
from datetime import datetime, timedelta


# ─────────────────────────────────────────────────────────────────────────────
# Data fetching
# ─────────────────────────────────────────────────────────────────────────────

def fetch_price_data(symbol: str) -> tuple[pd.DataFrame, str]:
    end   = datetime.now()
    start = end - timedelta(days=270)
    for suffix in [".TW", ".TWO"]:
        ticker = f"{symbol}{suffix}"
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df, ticker
    raise ValueError(f"找不到股票 {symbol} 的數據")


def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df['Close']
    high  = df['High']
    low   = df['Low']
    vol   = df['Volume']

    for period in [5, 20, 60, 200, 240]:
        df[f'MA{period}'] = (
            SMAIndicator(close, window=period).sma_indicator()
            if len(df) >= period else np.nan
        )

    stoch = StochasticOscillator(high, low, close, window=9, smooth_window=3)
    df['K'] = stoch.stoch()
    df['D'] = stoch.stoch_signal()

    macd_obj = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    df['MACD']        = macd_obj.macd()
    df['MACD_Signal'] = macd_obj.macd_signal()
    df['MACD_Hist']   = macd_obj.macd_diff()

    df['RSI']      = RSIIndicator(close, window=14).rsi()
    df['Vol_MA20'] = vol.rolling(20).mean()
    df['Ret1']     = close.pct_change()     # daily return

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Condition definitions
# ─────────────────────────────────────────────────────────────────────────────

def _cross_above(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a.shift(1) <= b.shift(1)) & (a > b)

def _cross_below(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a.shift(1) >= b.shift(1)) & (a < b)


def build_conditions(df: pd.DataFrame) -> dict[str, pd.Series]:
    """
    Define all candidate conditions as boolean Series indexed by df.index.
    Each condition is one candidate pattern we want to backtest.
    """
    c     = df['Close']
    k     = df['K']
    d     = df['D']
    macd  = df['MACD']
    msig  = df['MACD_Signal']
    mhist = df['MACD_Hist']
    rsi   = df['RSI']
    vol   = df['Volume']
    vma   = df['Vol_MA20']
    ret1  = df['Ret1']

    conds: dict[str, pd.Series] = {}

    # ── KD ──────────────────────────────────────────────────────────────────
    conds['KD黃金交叉']         = _cross_above(k, d)
    conds['KD死亡交叉']         = _cross_below(k, d)
    conds['KD黃金交叉(超賣區)'] = _cross_above(k, d) & (k < 25)
    conds['KD死亡交叉(超買區)'] = _cross_below(k, d) & (k > 75)
    conds['K值超賣(<20)']       = k < 20
    conds['K值超賣(<30)']       = (k >= 20) & (k < 30)
    conds['K值超買(>80)']       = k > 80
    conds['K值超買(70-80)']     = (k >= 70) & (k <= 80)
    conds['K低位回升(<40)']     = (k < 40) & (k > k.shift(1))
    conds['K高位回落(>60)']     = (k > 60) & (k < k.shift(1))

    # ── MACD ────────────────────────────────────────────────────────────────
    conds['MACD黃金交叉']         = _cross_above(macd, msig)
    conds['MACD死亡交叉']         = _cross_below(macd, msig)
    conds['MACD黃金交叉(零軸下)'] = _cross_above(macd, msig) & (macd < 0)
    conds['MACD死亡交叉(零軸上)'] = _cross_below(macd, msig) & (macd > 0)
    conds['MACD零軸上方']         = macd > 0
    conds['MACD零軸下方']         = macd < 0
    conds['MACD柱擴大(多頭)']     = (mhist > 0) & (mhist > mhist.shift(1))
    conds['MACD柱擴大(空頭)']     = (mhist < 0) & (mhist < mhist.shift(1))
    conds['MACD柱縮小(多轉弱)']   = (mhist > 0) & (mhist < mhist.shift(1))
    conds['MACD柱縮小(空轉弱)']   = (mhist < 0) & (mhist > mhist.shift(1))

    # ── RSI ─────────────────────────────────────────────────────────────────
    conds['RSI超賣(<30)']     = rsi < 30
    conds['RSI偏低(30-40)']   = (rsi >= 30) & (rsi < 40)
    conds['RSI中性(40-60)']   = (rsi >= 40) & (rsi <= 60)
    conds['RSI偏高(60-70)']   = (rsi > 60) & (rsi <= 70)
    conds['RSI超買(>70)']     = rsi > 70
    conds['RSI極度超買(>80)'] = rsi > 80
    conds['RSI低位回升']      = (rsi < 45) & (rsi > rsi.shift(1))
    conds['RSI高位回落']      = (rsi > 55) & (rsi < rsi.shift(1))

    # ── Moving Averages ──────────────────────────────────────────────────────
    for period, label in [(5, '5MA'), (20, '月線20MA'), (60, '季線60MA'), (200, '200MA')]:
        col = f'MA{period}'
        if col not in df.columns or df[col].isna().all():
            continue
        ma = df[col]
        conds[f'站上{label}']  = c > ma
        conds[f'跌破{label}']  = c < ma
        conds[f'突破{label}↑'] = _cross_above(c, ma)
        conds[f'跌破{label}↓'] = _cross_below(c, ma)

    # ── Volume ──────────────────────────────────────────────────────────────
    high_vol = vol > vma * 1.5
    conds['爆量上漲'] = high_vol & (ret1 > 0)
    conds['爆量下跌'] = high_vol & (ret1 < 0)
    conds['縮量上漲'] = (vol < vma * 0.7) & (ret1 > 0)
    conds['縮量下跌'] = (vol < vma * 0.7) & (ret1 < 0)

    # ── Compound ─────────────────────────────────────────────────────────────
    conds['KD超賣+MACD金叉']  = (k < 30) & _cross_above(macd, msig)
    conds['KD超買+MACD死叉']  = (k > 70) & _cross_below(macd, msig)
    conds['跌破月線+MACD死叉'] = _cross_below(c, df.get('MA20', pd.Series(np.nan, index=df.index))) & _cross_below(macd, msig)
    conds['突破月線+MACD金叉'] = _cross_above(c, df.get('MA20', pd.Series(np.nan, index=df.index))) & _cross_above(macd, msig)

    # Cast all to bool, fill NaN → False
    return {name: s.fillna(False).astype(bool) for name, s in conds.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Backtest engine
# ─────────────────────────────────────────────────────────────────────────────

HORIZON     = 5     # trading days forward
MOVE_THRESH = 0.015 # ±1.5% counts as significant move
MIN_SAMPLES = 4     # minimum occurrences to trust a condition

# Condition → indicator group mapping (for deduplication)
COND_GROUPS: dict[str, str] = {}  # populated lazily by _group_of()

def _group_of(name: str) -> str:
    if name.startswith(('KD', 'K值', 'K低', 'K高')):   return 'KD'
    if name.startswith('MACD'):                          return 'MACD'
    if name.startswith('RSI'):                           return 'RSI'
    if '5MA' in name or '5ma' in name.lower():           return 'MA5'
    if '月線' in name or '20MA' in name:                 return 'MA20'
    if '季線' in name or '60MA' in name:                 return 'MA60'
    if '200MA' in name:                                  return 'MA200'
    if '量' in name:                                     return 'Volume'
    return 'Compound'


def compute_outcomes(df: pd.DataFrame) -> pd.Series:
    """5-day forward return label: 1=up, -1=down, 0=flat, NaN=unknown."""
    close = df['Close']
    fwd   = (close.shift(-HORIZON) - close) / close
    out   = pd.Series(np.nan, index=df.index, dtype=float)
    out[fwd >  MOVE_THRESH] =  1.0
    out[fwd < -MOVE_THRESH] = -1.0
    out[(fwd >= -MOVE_THRESH) & (fwd <= MOVE_THRESH)] = 0.0
    return out


def backtest_conditions(
    conditions: dict[str, pd.Series],
    outcomes:   pd.Series,
    base:       dict,
) -> dict[str, dict]:
    """
    For each condition, compute historical up/down rates when it was active.
    Uses EXCESS edge (condition_edge − baseline_edge) so that bull-market bias
    does not inflate scores.
    Returns only conditions with >= MIN_SAMPLES occurrences.
    """
    known        = outcomes.dropna()
    base_edge    = base['up_rate'] - base['down_rate']
    results: dict[str, dict] = {}

    for name, cond in conditions.items():
        aligned = cond.reindex(known.index).fillna(False)
        hits    = known[aligned]
        n       = len(hits)
        if n < MIN_SAMPLES:
            continue
        up   = float((hits ==  1).mean())
        down = float((hits == -1).mean())
        flat = float((hits ==  0).mean())
        edge        = up - down
        excess_edge = edge - base_edge        # how much better/worse than doing nothing
        conf        = min(n / 20.0, 1.0)     # confidence saturates at 20 samples
        results[name] = {
            'count':       n,
            'up_rate':     up,
            'down_rate':   down,
            'flat_rate':   flat,
            'edge':        edge,
            'excess_edge': excess_edge,
            'confidence':  conf,
            'weight':      excess_edge * conf, # effective score contribution
            'group':       _group_of(name),
        }

    return results


def baseline_stats(outcomes: pd.Series) -> dict:
    known = outcomes.dropna()
    return {
        'count':     len(known),
        'up_rate':   float((known == 1).mean()),
        'down_rate': float((known == -1).mean()),
        'flat_rate': float((known == 0).mean()),
        'edge':      float((known == 1).mean()) - float((known == -1).mean()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Institutional (三大法人) — TWSE / TPEx
# ─────────────────────────────────────────────────────────────────────────────

_TWSE_HDR = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.twse.com.tw/'}
_TPEX_HDR = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.tpex.org.tw/'}


def _parse_num(s: str) -> int:
    try:
        return int(str(s).replace(',', '').replace(' ', ''))
    except (ValueError, AttributeError):
        return 0


def _fetch_twse_day(date_str: str, symbol: str) -> dict | None:
    try:
        r = requests.get(
            'https://www.twse.com.tw/rwd/zh/fund/T86',
            params={'response': 'json', 'date': date_str, 'selectType': 'ALLBUT0999'},
            headers=_TWSE_HDR, timeout=12,
        )
        d = r.json()
        if d.get('stat') != 'OK':
            return None
        for row in d.get('data', []):
            if str(row[0]).strip() == symbol:
                return {
                    'date':    date_str,
                    'foreign': _parse_num(row[4]) + _parse_num(row[7]),
                    'trust':   _parse_num(row[10]),
                    'dealer':  _parse_num(row[11]),
                    'total':   _parse_num(row[18]),
                }
    except Exception:
        pass
    return None


def _fetch_tpex_day(date_str: str, symbol: str) -> dict | None:
    try:
        tpex_date = datetime.strptime(date_str, '%Y%m%d').strftime('%Y/%m/%d')
        r = requests.get(
            'https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php',
            params={'l': 'zh-tw', 'o': 'json', 'se': 'EW', 't': 'D', 'd': tpex_date},
            headers=_TPEX_HDR, timeout=12,
        )
        d = r.json()
        for row in (d.get('aaData') or d.get('data', [])):
            if str(row[0]).strip() == symbol:
                return {
                    'date':    date_str,
                    'foreign': _parse_num(row[4]) + _parse_num(row[7]),
                    'trust':   _parse_num(row[10]),
                    'dealer':  _parse_num(row[13]),
                    'total':   _parse_num(row[17]),
                }
    except Exception:
        pass
    return None


def fetch_institutional(symbol: str, is_otc: bool = False, n_days: int = 20) -> pd.DataFrame:
    fn       = _fetch_tpex_day if is_otc else _fetch_twse_day
    dates    = [(datetime.now() - timedelta(days=i)).strftime('%Y%m%d') for i in range(1, 55)]
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fn, dt, symbol): dt for dt in dates}
        for fut in as_completed(futures):
            row = fut.result()
            if row:
                results.append(row)
            if len(results) >= n_days:
                for f in futures:
                    f.cancel()
                break

    if not results:
        return pd.DataFrame()
    return (
        pd.DataFrame(results)
        .sort_values('date', ascending=False)
        .reset_index(drop=True)
        .head(n_days)
    )


def _consecutive(lst: list[int]) -> tuple[int, int]:
    buy = sell = 0
    for v in lst:
        if v > 0:
            if sell: break
            buy += 1
        elif v < 0:
            if buy: break
            sell += 1
        else:
            break
    return buy, sell


def analyze_institutional(df_inst: pd.DataFrame) -> tuple[int, list[tuple], dict]:
    if df_inst.empty:
        return 0, [], {}

    foreign = df_inst['foreign'].tolist()
    trust   = df_inst['trust'].tolist()
    total   = df_inst['total'].tolist()

    cum5 = lambda lst: sum(lst[:5]) // 10_000
    f5, t5, tot5 = cum5(foreign), cum5(trust), cum5(total)
    f10 = sum(foreign[:10]) // 10_000 if len(foreign) >= 10 else None

    f_buy, f_sell = _consecutive(foreign)
    t_buy, t_sell = _consecutive(trust)

    score   = 0
    signals: list[tuple] = []

    if f_buy >= 3:
        score += 2; signals.append(("外資", f"連續買超 {f_buy} 日，近5日累積 {f5:+,} 萬股"))
    elif f_buy >= 1:
        score += 1; signals.append(("外資", f"買超 {f_buy} 日，近5日累積 {f5:+,} 萬股"))
    elif f_sell >= 3:
        score -= 2; signals.append(("外資", f"連續賣超 {f_sell} 日，近5日累積 {f5:+,} 萬股"))
    elif f_sell >= 1:
        score -= 1; signals.append(("外資", f"賣超 {f_sell} 日，近5日累積 {f5:+,} 萬股"))

    if t_buy >= 3:
        score += 2; signals.append(("投信", f"連續買超 {t_buy} 日，近5日累積 {t5:+,} 萬股"))
    elif t_buy >= 1:
        score += 1; signals.append(("投信", f"買超 {t_buy} 日，近5日累積 {t5:+,} 萬股"))
    elif t_sell >= 3:
        score -= 2; signals.append(("投信", f"連續賣超 {t_sell} 日，近5日累積 {t5:+,} 萬股"))
    elif t_sell >= 1:
        score -= 1; signals.append(("投信", f"賣超 {t_sell} 日，近5日累積 {t5:+,} 萬股"))

    if f_buy >= 1 and t_buy >= 1:
        score += 1; signals.append(("同買", "外資+投信同步買超，籌碼集中"))
    elif f_sell >= 1 and t_sell >= 1:
        score -= 1; signals.append(("同賣", "外資+投信同步賣超，賣壓沉重"))

    if f10 is not None:
        tag = "外資10日"
        if f10 > 0:
            signals.append((tag, f"近10日累積買超 {f10:,} 萬股，中期偏多"))
        else:
            signals.append((tag, f"近10日累積賣超 {f10:,} 萬股，中期偏空"))

    summary = {
        'f5': f5, 't5': t5, 'tot5': tot5,
        'f_buy': f_buy, 'f_sell': f_sell,
        't_buy': t_buy, 't_sell': t_sell,
        'f_today':   foreign[0] // 10_000 if foreign else 0,
        't_today':   trust[0]   // 10_000 if trust   else 0,
        'tot_today': total[0]   // 10_000 if total   else 0,
    }
    return score, signals, summary


# ─────────────────────────────────────────────────────────────────────────────
# Main analysis
# ─────────────────────────────────────────────────────────────────────────────

def analyze(
    df:       pd.DataFrame,
    symbol:   str,
    df_inst:  pd.DataFrame,
) -> dict:
    if len(df) < 30:
        raise ValueError("歷史數據不足")

    # ── Build conditions & run backtest ─────────────────────────────────────
    conditions = build_conditions(df)
    outcomes   = compute_outcomes(df)
    base       = baseline_stats(outcomes)
    bt         = backtest_conditions(conditions, outcomes, base)

    # ── Which conditions are active today (last row) ─────────────────────────
    today_flags: dict[str, bool] = {
        name: bool(cond.iloc[-1]) for name, cond in conditions.items()
    }

    # ── Score: one best signal per indicator group (prevents double-counting) ─
    # For each group, pick the active condition with the highest |weight|.
    # Sum those per-group bests → tech_score.
    group_best: dict[str, dict] = {}  # group → best active condition stats
    active_bt:  list[dict]       = []

    for name, stats in bt.items():
        if not today_flags.get(name, False):
            continue
        entry  = {'name': name, **stats}
        active_bt.append(entry)
        grp    = stats['group']
        if grp not in group_best or abs(stats['weight']) > abs(group_best[grp]['weight']):
            group_best[grp] = entry

    tech_score = sum(s['weight'] for s in group_best.values())
    active_bt.sort(key=lambda x: abs(x['weight']), reverse=True)

    # ── Institutional signals ────────────────────────────────────────────────
    inst_score, inst_signals, inst_summary = analyze_institutional(df_inst)
    # Normalize inst_score (-5..+5) to similar scale as tech_score
    inst_normalized = inst_score * 0.12

    combined = tech_score + inst_normalized

    # ── Recommendation ───────────────────────────────────────────────────────
    if combined >= 0.6:
        recommendation = "強力加碼"
    elif combined >= 0.25:
        recommendation = "加碼"
    elif combined <= -0.6:
        recommendation = "強力減碼"
    elif combined <= -0.25:
        recommendation = "減碼"
    else:
        recommendation = "持平"

    # ── Snapshot values ──────────────────────────────────────────────────────
    def _s(col):
        v = df[col].iloc[-1]
        return None if pd.isna(v) else float(v)

    price     = _s('Close')
    prev_p    = float(df['Close'].iloc[-2])
    price_chg = (price - prev_p) if price else None
    price_pct = (price_chg / prev_p * 100) if price_chg else None

    return {
        'symbol':         symbol,
        'price':          price,
        'price_chg':      price_chg,
        'price_pct':      price_pct,
        'K':   _s('K'),   'D':          _s('D'),
        'RSI': _s('RSI'), 'MACD':       _s('MACD'),
        'MACD_Signal':    _s('MACD_Signal'),
        'MA5':  _s('MA5'),  'MA20': _s('MA20'),
        'MA60': _s('MA60'), 'MA200': _s('MA200'),
        'base':           base,
        'active_bt':      active_bt,
        'group_best':     group_best,
        'all_bt':         bt,
        'tech_score':     tech_score,
        'inst_score':     inst_score,
        'combined':       combined,
        'recommendation': recommendation,
        'inst_signals':   inst_signals,
        'inst_summary':   inst_summary,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Report formatting
# ─────────────────────────────────────────────────────────────────────────────

def _direction_label(excess: float, n: int) -> str:
    """Label a condition based on its excess edge vs baseline."""
    # Require minimum statistical confidence: penalise small samples
    effective = excess * min(n / 10.0, 1.0)
    if effective >= +0.20:  return "強多 ↑↑"
    if effective >= +0.10:  return "多  ↑ "
    if effective <= -0.20:  return "強空 ↓↓"
    if effective <= -0.10:  return "空  ↓ "
    return "中性 → "


def fmt_report(r: dict) -> str:
    W = 70
    lines: list[str] = []

    def _v(x, fmt='.2f'):
        return f"{x:{fmt}}" if x is not None else "N/A"

    lines.append("=" * W)
    lines.append(f"  股票代號: {r['symbol']}")
    chg = f"  ({r['price_chg']:+.2f}, {r['price_pct']:+.2f}%)" if r['price_chg'] else ""
    lines.append(f"  最新收盤: {_v(r['price'])}{chg}")

    # ── Indicator snapshot ────────────────────────────────────────────────────
    lines.append("-" * W)
    lines.append("  技術指標快照:")
    lines.append(f"    KD:   K={_v(r['K'],'.1f')}  D={_v(r['D'],'.1f')}")
    lines.append(f"    RSI:  {_v(r['RSI'],'.1f')}")
    lines.append(f"    MACD: {_v(r['MACD'],'.3f')}  Signal: {_v(r['MACD_Signal'],'.3f')}")
    ma_parts = []
    for key, lbl in [('MA5','5MA'),('MA20','20MA'),('MA60','60MA'),('MA200','200MA')]:
        if r[key] is not None:
            ma_parts.append(f"{lbl}={_v(r[key])}")
    lines.append(f"    均線: {'  '.join(ma_parts)}")

    # ── Institutional snapshot ────────────────────────────────────────────────
    inst = r.get('inst_summary', {})
    if inst:
        lines.append("-" * W)
        lines.append("  三大法人 (近5日累積，萬股):")

        def streak(b, s):
            return f"連買{b}日" if b else (f"連賣{s}日" if s else "持平")

        lines.append(
            f"    外資: 今日{inst['f_today']:+,}萬股  近5日{inst['f5']:+,}萬股"
            f"  [{streak(inst['f_buy'],inst['f_sell'])}]"
        )
        lines.append(
            f"    投信: 今日{inst['t_today']:+,}萬股  近5日{inst['t5']:+,}萬股"
            f"  [{streak(inst['t_buy'],inst['t_sell'])}]"
        )
        lines.append(
            f"    三大合計: 今日{inst['tot_today']:+,}萬股  近5日{inst['tot5']:+,}萬股"
        )

    # ── Backtested technical signals table ───────────────────────────────────
    base = r['base']
    lines.append("-" * W)
    lines.append(
        f"  歷史回測 ({base['count']} 個交易日 | 目標: 5日後漲跌>{MOVE_THRESH*100:.0f}%"
        f" | 基準: 上漲{base['up_rate']*100:.0f}% 下跌{base['down_rate']*100:.0f}%)"
    )
    lines.append("")

    # Determine which conditions actually contributed to the score (one per group)
    scoring_names = {s['name'] for s in r['group_best'].values()}

    col_w = [27, 5, 5, 7, 7, 8, 10]
    header = (
        f"  {'條件':<{col_w[0]}} {'次數':>{col_w[1]}} {'觸發':>{col_w[2]}}"
        f" {'上漲率':>{col_w[3]}} {'下跌率':>{col_w[4]}} {'超額邊際':>{col_w[5]}} {'結論':<{col_w[6]}}"
    )
    lines.append(header)
    lines.append("  " + "─" * (W - 2))

    all_bt       = r['all_bt']
    active_names = {s['name'] for s in r['active_bt']}

    def sort_key(item):
        name, stats = item
        # Active conditions first (sorted by |excess_edge|), then inactive
        return (0 if name in active_names else 1, -abs(stats['excess_edge']))

    for name, stats in sorted(all_bt.items(), key=sort_key):
        is_active  = name in active_names
        is_scoring = name in scoring_names
        if is_active and is_scoring:
            marker = " ★"   # active + scored
        elif is_active:
            marker = " ✓"   # active but group already covered by a better condition
        else:
            marker = "  "
        up_pct  = stats['up_rate']  * 100
        down_pct = stats['down_rate'] * 100
        excess  = stats['excess_edge']
        direction = _direction_label(excess, stats['count'])
        lines.append(
            f"  {name:<{col_w[0]}} {stats['count']:>{col_w[1]}} {marker:>{col_w[2]}}"
            f" {up_pct:>{col_w[3]}.0f}% {down_pct:>{col_w[4]}.0f}%"
            f" {excess:>+{col_w[5]}.3f} {direction:<{col_w[6]}}"
        )

    lines.append(f"  (★=計入評分 ✓=觸發但同組已有更強信號  超額邊際=條件邊際−基準{base['edge']:+.2f})")

    # ── Institutional signals ─────────────────────────────────────────────────
    if r['inst_signals']:
        lines.append("")
        lines.append("  [籌碼面]")
        for tag, desc in r['inst_signals']:
            lines.append(f"    [{tag}] {desc}")

    # ── Verdict ───────────────────────────────────────────────────────────────
    lines.append("-" * W)
    lines.append(
        f"  技術分數: {r['tech_score']:+.3f}  "
        f"籌碼分數: {r['inst_score']:+d}(×0.12={r['inst_score']*0.12:+.2f})  "
        f"合計: {r['combined']:+.3f}"
    )
    rec  = r['recommendation']
    icon = {"強力加碼": "🚀", "加碼": "↑", "持平": "→", "減碼": "↓", "強力減碼": "⚠"}.get(rec, "")
    lines.append(f"  ▶ 未來一週建議: 【{rec}】 {icon}")
    lines.append("=" * W)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法: python3 tech_analysis.py <代號1> [代號2] ...")
        print("範例: python3 tech_analysis.py 2330 2317 0050")
        sys.exit(1)

    for sym in sys.argv[1:]:
        sym = sym.strip().upper()
        try:
            print(f"\n正在抓取 {sym} 價格數據...")
            df, ticker = fetch_price_data(sym)
            is_otc = ticker.endswith('.TWO')
            df = calc_indicators(df)

            print(f"正在抓取 {sym} 三大法人數據...")
            df_inst = fetch_institutional(sym, is_otc=is_otc)

            result = analyze(df, sym, df_inst)
            print(fmt_report(result))
        except Exception as e:
            import traceback
            print(f"[錯誤] {sym}: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
