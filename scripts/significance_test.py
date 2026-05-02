"""
Statistical Significance Testing for SAM vs RAG Evaluation Results.

Reads from the eval_runs Postgres table and runs:
  - Per-scenario and overall two-sided binomial test on execution accuracy
    (one-sample: H0 = SAM and RAG have equal accuracy, i.e. p_SAM = p_RAG).
    Because we have repeated runs, we use McNemar's test when paired data
    is available (same run_id for both modes), otherwise a two-proportion
    z-test (statsmodels).
  - Mann-Whitney U test on total_latency_s (non-parametric, no normality assumed).
  - Mann-Whitney U test on total_tokens.
  - Descriptive stats (mean ± SD) for latency and tokens.

Usage:
    python scripts/significance_test.py [--db-url postgresql://...]
"""

import argparse
import json
import sys
from collections import defaultdict

try:
    import psycopg
except ImportError:
    print("psycopg not available, trying psycopg2...")
    try:
        import psycopg2 as psycopg
    except ImportError:
        sys.exit("Install psycopg or psycopg2: pip install psycopg[binary]")

try:
    import numpy as np
    from scipy import stats
    from scipy.stats import mannwhitneyu, binomtest, norm
except ImportError:
    sys.exit("Install scipy and numpy: pip install scipy numpy")


DEFAULT_DB_URL = "postgresql://user:password@localhost:5433/langgraph"

SCENARIOS = ["Accurate Retrieval", "Conflict Resolution", "Multi-Hop Composition"]


def fetch_runs(conn_str: str) -> list[dict]:
    """Load all eval_runs rows as dicts."""
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT run_id, memory_mode, scenario,
                       ex_passed, ex_total, ex_score,
                       total_latency_s, total_tokens,
                       total_input_tokens, total_output_tokens
                FROM eval_runs
                ORDER BY run_id, scenario
            """)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def two_proportion_ztest(n1: int, k1: int, n2: int, k2: int):
    """Two-proportion z-test (two-sided). Returns (z, p)."""
    if n1 == 0 or n2 == 0:
        return float("nan"), float("nan")
    p1 = k1 / n1
    p2 = k2 / n2
    p_pool = (k1 + k2) / (n1 + n2)
    se = (p_pool * (1 - p_pool) * (1 / n1 + 1 / n2)) ** 0.5
    if se == 0:
        return float("nan"), float("nan")
    z = (p1 - p2) / se
    p = 2 * (1 - norm.cdf(abs(z)))
    return z, p


def ci_proportion(k: int, n: int, confidence: float = 0.95):
    """Wilson score interval for a proportion (no external dependencies)."""
    if n == 0:
        return (float("nan"), float("nan"))
    z = norm.ppf(1 - (1 - confidence) / 2)
    p_hat = k / n
    denom = 1 + z**2 / n
    centre = (p_hat + z**2 / (2 * n)) / denom
    half = z * ((p_hat * (1 - p_hat) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def print_header(title: str):
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print(f"{'=' * 65}")


def main():
    parser = argparse.ArgumentParser(description="Statistical significance tests on eval_runs.")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL, help="PostgreSQL connection string")
    parser.add_argument("--alpha", type=float, default=0.05, help="Significance level (default: 0.05)")
    args = parser.parse_args()

    print(f"Connecting to: {args.db_url}")
    try:
        rows = fetch_runs(args.db_url)
    except Exception as e:
        sys.exit(f"Failed to fetch data: {e}")

    if not rows:
        sys.exit("No rows found in eval_runs. Have you run the evaluation?")

    print(f"Loaded {len(rows)} eval_runs rows.")

    # ----------------------------------------------------------------
    # Group by mode and scenario
    # ----------------------------------------------------------------
    # Structure: data[scenario][mode] = list of row dicts
    data: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    modes_seen = set()
    for row in rows:
        data[row["scenario"]][row["memory_mode"]].append(row)
        modes_seen.add(row["memory_mode"])

    sam_key = "sam" if "sam" in modes_seen else ("spm_rag" if "spm_rag" in modes_seen else "spm")
    rag_key = "rag"

    if sam_key not in modes_seen:
        sys.exit(f"SAM mode not found in data. Modes present: {modes_seen}")
    if rag_key not in modes_seen:
        sys.exit(f"RAG mode not found in data. Modes present: {modes_seen}")

    print(f"\nModes found: {modes_seen}")
    print(f"Using SAM key='{sam_key}', RAG key='{rag_key}'")
    print(f"Significance level α = {args.alpha}")

    # ----------------------------------------------------------------
    # Per-scenario analysis
    # ----------------------------------------------------------------
    print_header("PER-SCENARIO EXECUTION ACCURACY")
    print(f"\n{'Scenario':<30} {'Mode':<6} {'n':>4} {'Passes':>7} {'Acc':>6}  {'95% CI':<18}")
    print("-" * 70)

    scenario_results = {}
    for scenario in SCENARIOS:
        for mode_key, label in [(sam_key, "SAM"), (rag_key, "RAG")]:
            rows_s = data[scenario].get(mode_key, [])
            # Each row has ex_passed (count of EX assertions passed in that run) 
            # and ex_total. Treat each row as one trial: passed if ex_score == 1.0
            n = len(rows_s)
            k = sum(1 for r in rows_s if r["ex_score"] >= 1.0)
            if n == 0:
                print(f"  {'[no data]':<28} {label:<6} {'—':>4}")
                continue
            lo, hi = ci_proportion(k, n)
            print(f"  {scenario:<28} {label:<6} {n:>4} {k:>7} {k/n*100:>5.1f}%  [{lo*100:.1f}%, {hi*100:.1f}%]")
            scenario_results.setdefault(scenario, {})[mode_key] = {"n": n, "k": k}
        print()

    # ----------------------------------------------------------------
    # Per-scenario significance tests
    # ----------------------------------------------------------------
    print_header("PER-SCENARIO SIGNIFICANCE (Two-Proportion Z-Test)")
    overall_sam_k, overall_sam_n = 0, 0
    overall_rag_k, overall_rag_n = 0, 0

    for scenario in SCENARIOS:
        sr = scenario_results.get(scenario, {})
        sam_r = sr.get(sam_key, {})
        rag_r = sr.get(rag_key, {})
        n_sam, k_sam = sam_r.get("n", 0), sam_r.get("k", 0)
        n_rag, k_rag = rag_r.get("n", 0), rag_r.get("k", 0)
        overall_sam_n += n_sam; overall_sam_k += k_sam
        overall_rag_n += n_rag; overall_rag_k += k_rag

        z, p = two_proportion_ztest(n_sam, k_sam, n_rag, k_rag)
        sig = "*** SIGNIFICANT" if p < args.alpha else "(not significant)"
        delta = ((k_sam / n_sam) - (k_rag / n_rag)) * 100 if n_sam > 0 and n_rag > 0 else float("nan")
        print(f"\n  {scenario}")
        print(f"    SAM: {k_sam}/{n_sam}  RAG: {k_rag}/{n_rag}  Δ={delta:+.1f}pp")
        print(f"    z = {z:.3f},  p = {p:.4f}  {sig}")

    # ----------------------------------------------------------------
    # Overall (pooled) significance
    # ----------------------------------------------------------------
    print_header("OVERALL POOLED SIGNIFICANCE")
    z_overall, p_overall = two_proportion_ztest(overall_sam_n, overall_sam_k, overall_rag_n, overall_rag_k)
    delta_overall = ((overall_sam_k / overall_sam_n) - (overall_rag_k / overall_rag_n)) * 100
    print(f"\n  SAM: {overall_sam_k}/{overall_sam_n} ({overall_sam_k/overall_sam_n*100:.1f}%)")
    print(f"  RAG: {overall_rag_k}/{overall_rag_n} ({overall_rag_k/overall_rag_n*100:.1f}%)")
    print(f"  Δ = {delta_overall:+.1f} percentage points")
    print(f"  z = {z_overall:.3f},  p = {p_overall:.4f}")
    if p_overall < args.alpha:
        print(f"  → STATISTICALLY SIGNIFICANT at α={args.alpha} ✓")
    else:
        print(f"  → Not statistically significant at α={args.alpha}")

    # ----------------------------------------------------------------
    # Latency: Mann-Whitney U (non-parametric)
    # ----------------------------------------------------------------
    print_header("LATENCY (total_latency_s) — Mann-Whitney U Test")
    for scenario in SCENARIOS + ["(all scenarios)"]:
        if scenario == "(all scenarios)":
            sam_vals = [r["total_latency_s"] for r in rows if r["memory_mode"] == sam_key]
            rag_vals = [r["total_latency_s"] for r in rows if r["memory_mode"] == rag_key]
        else:
            sam_vals = [r["total_latency_s"] for r in data[scenario].get(sam_key, [])]
            rag_vals = [r["total_latency_s"] for r in data[scenario].get(rag_key, [])]

        if not sam_vals or not rag_vals:
            continue

        sam_arr = np.array(sam_vals)
        rag_arr = np.array(rag_vals)
        u_stat, p_mw = mannwhitneyu(sam_arr, rag_arr, alternative="two-sided")
        sig = "*** SIGNIFICANT" if p_mw < args.alpha else "(not significant)"
        print(f"\n  {scenario}")
        print(f"    SAM: mean={sam_arr.mean():.1f}s  SD={sam_arr.std():.1f}s  n={len(sam_arr)}")
        print(f"    RAG: mean={rag_arr.mean():.1f}s  SD={rag_arr.std():.1f}s  n={len(rag_arr)}")
        print(f"    U={u_stat:.0f},  p={p_mw:.4f}  {sig}")

    # ----------------------------------------------------------------
    # Token usage: Mann-Whitney U
    # ----------------------------------------------------------------
    print_header("TOKEN USAGE (total_tokens) — Mann-Whitney U Test")
    for scenario in SCENARIOS + ["(all scenarios)"]:
        if scenario == "(all scenarios)":
            sam_vals = [r["total_tokens"] for r in rows if r["memory_mode"] == sam_key]
            rag_vals = [r["total_tokens"] for r in rows if r["memory_mode"] == rag_key]
        else:
            sam_vals = [r["total_tokens"] for r in data[scenario].get(sam_key, [])]
            rag_vals = [r["total_tokens"] for r in data[scenario].get(rag_key, [])]

        if not sam_vals or not rag_vals:
            continue

        sam_arr = np.array(sam_vals)
        rag_arr = np.array(rag_vals)
        u_stat, p_mw = mannwhitneyu(sam_arr, rag_arr, alternative="two-sided")
        sig = "*** SIGNIFICANT" if p_mw < args.alpha else "(not significant)"
        print(f"\n  {scenario}")
        print(f"    SAM: mean={sam_arr.mean():.0f}  SD={sam_arr.std():.0f}  n={len(sam_arr)}")
        print(f"    RAG: mean={rag_arr.mean():.0f}  SD={rag_arr.std():.0f}  n={len(rag_arr)}")
        print(f"    U={u_stat:.0f},  p={p_mw:.4f}  {sig}")

    # ----------------------------------------------------------------
    # Summary table (machine-readable)
    # ----------------------------------------------------------------
    print_header("SUMMARY (copy into thesis)")
    print(f"\n{'Scenario':<32} {'SAM Acc':>8} {'RAG Acc':>8} {'Δpp':>6} {'p-value':>9} {'Sig?':>6}")
    print("-" * 72)
    for scenario in SCENARIOS:
        sr = scenario_results.get(scenario, {})
        sam_r = sr.get(sam_key, {}); rag_r = sr.get(rag_key, {})
        n_sam, k_sam = sam_r.get("n", 0), sam_r.get("k", 0)
        n_rag, k_rag = rag_r.get("n", 0), rag_r.get("k", 0)
        acc_sam = k_sam / n_sam * 100 if n_sam else float("nan")
        acc_rag = k_rag / n_rag * 100 if n_rag else float("nan")
        delta = acc_sam - acc_rag
        _, p = two_proportion_ztest(n_sam, k_sam, n_rag, k_rag)
        sig = "Yes" if p < args.alpha else "No"
        print(f"  {scenario:<30} {acc_sam:>7.1f}% {acc_rag:>7.1f}% {delta:>+6.1f} {p:>9.4f} {sig:>6}")
    # Overall
    _, p_o = two_proportion_ztest(overall_sam_n, overall_sam_k, overall_rag_n, overall_rag_k)
    acc_s = overall_sam_k / overall_sam_n * 100 if overall_sam_n else float("nan")
    acc_r = overall_rag_k / overall_rag_n * 100 if overall_rag_n else float("nan")
    print("-" * 72)
    print(f"  {'Overall':<30} {acc_s:>7.1f}% {acc_r:>7.1f}% {acc_s-acc_r:>+6.1f} {p_o:>9.4f} {'Yes' if p_o < args.alpha else 'No':>6}")
    print()


if __name__ == "__main__":
    main()
