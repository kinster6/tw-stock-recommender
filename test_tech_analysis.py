#!/usr/bin/env python3
"""Self-check for tech_analysis.py's multi-stock summary sort (ponytail: non-trivial multi-key sort)."""
from tech_analysis import fmt_summary_table, _REC_RANK

FAKE_RESULTS = [
    {'symbol': 'A', 'company_name': 'AA', 'price': 100.0, 'tech_score': 0.1,
     'inst_score': 0, 'combined': -0.1, 'recommendation': '持平'},
    {'symbol': 'B', 'company_name': 'BB', 'price': 200.0, 'tech_score': 0.5,
     'inst_score': 3, 'combined': 0.9, 'recommendation': '強力加碼'},
    {'symbol': 'C', 'company_name': 'CC', 'price': 300.0, 'tech_score': 0.2,
     'inst_score': 0, 'combined': 0.3, 'recommendation': '加碼'},
    {'symbol': 'D', 'company_name': 'DD', 'price': 50.0, 'tech_score': -0.8,
     'inst_score': -3, 'combined': -0.7, 'recommendation': '強力減碼'},
    {'symbol': 'E', 'company_name': 'EE', 'price': 60.0, 'tech_score': 0.6,
     'inst_score': 3, 'combined': 1.2, 'recommendation': '強力加碼'},
]


def test_sorted_by_recommendation_tier_then_score_descending():
    table = fmt_summary_table(FAKE_RESULTS)
    order = [line.split()[0] for line in table.splitlines() if line.strip()[:1].isalpha()
             and line.strip()[0] in 'ABCDE']
    # Two 強力加碼 rows: E (combined 1.2) must outrank B (combined 0.9); then 加碼 C;
    # then 持平 A; then 強力減碼 D last.
    assert order == ['E', 'B', 'C', 'A', 'D'], order


def test_rec_rank_is_strictly_descending_bull_to_bear():
    tiers = ['強力加碼', '加碼', '持平', '減碼', '強力減碼']
    ranks = [_REC_RANK[t] for t in tiers]
    assert ranks == sorted(ranks, reverse=True)


if __name__ == "__main__":
    test_sorted_by_recommendation_tier_then_score_descending()
    test_rec_rank_is_strictly_descending_bull_to_bear()
    print("OK: all tech_analysis summary-table checks passed")
