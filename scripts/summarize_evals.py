#!/usr/bin/env python3
import os
import sys
import json
import argparse
import psycopg
from pathlib import Path
from psycopg.rows import dict_row

from google import genai

DB_URL = "postgresql://user:password@localhost:5433/langgraph"

from datetime import datetime

class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()

def main():
    parser = argparse.ArgumentParser(description="Summarize eval runs for a given memory mode.")
    parser.add_argument("mode", help="Memory mode to summarize (e.g., sam, rag)")
    parser.add_argument("--model", default="gemini-3.1-pro-preview", help="Model to use for summarization")
    parser.add_argument("--output", help="Optional file path to save the summary report", default=None)
    parser.add_argument(
        "--after",
        default=None,
        metavar="DATE",
        help="Only include runs created after this date (inclusive). Format: YYYY-MM-DD",
    )
    args = parser.parse_args()

    # Validate --after date
    after_dt = None
    if args.after:
        try:
            after_dt = datetime.strptime(args.after, "%Y-%m-%d")
        except ValueError:
            print(f"Error: --after value '{args.after}' is not a valid date. Expected format: YYYY-MM-DD")
            sys.exit(1)

    # Setup automatic saving to file
    out_path = args.output
    if not out_path:
        os.makedirs("results", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = f"results/summary_{args.mode}_{timestamp}.txt"
    
    out_file = open(out_path, "w", encoding="utf-8")
    sys.stdout = Tee(sys.stdout, out_file)

    print(f"📝 Logging results to: {out_path}\n")

    # 1. Fetch runs from DB
    try:
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if after_dt:
                    cur.execute(
                        "SELECT * FROM eval_runs WHERE memory_mode = %s AND created_at >= %s",
                        (args.mode, after_dt),
                    )
                else:
                    cur.execute("SELECT * FROM eval_runs WHERE memory_mode = %s", (args.mode,))
                rows = cur.fetchall()
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

    if not rows:
        date_hint = f" after {args.after}" if args.after else ""
        print(f"No runs found for mode: '{args.mode}'{date_hint}")
        sys.exit(0)

    # 2. Calculate Aggregate & Per-Scenario Statistics
    total_runs = len(rows)
    
    # Per-scenario stats
    scenario_stats = {}
    for r in rows:
        scen = r.get("scenario", "Unknown")
        if scen not in scenario_stats:
            scenario_stats[scen] = {"runs": 0, "ex_passed": 0, "ex_total": 0, "latency": 0, "tokens": 0}
        
        scenario_stats[scen]["runs"] += 1
        scenario_stats[scen]["ex_passed"] += (r.get("ex_passed") or 0)
        scenario_stats[scen]["ex_total"] += (r.get("ex_total") or 0)
        scenario_stats[scen]["latency"] += (r.get("total_latency_s") or 0)
        scenario_stats[scen]["tokens"] += (r.get("total_tokens") or 0)

    # Aggregate stats
    total_latency = sum(r.get("total_latency_s") or 0 for r in rows)
    avg_latency = total_latency / total_runs if total_runs else 0
    total_input = sum(r.get("total_input_tokens") or 0 for r in rows)
    total_output = sum(r.get("total_output_tokens") or 0 for r in rows)
    total_tokens = sum(r.get("total_tokens") or 0 for r in rows)
    ex_passed_total = sum(r.get("ex_passed") or 0 for r in rows)
    ex_expected_total = sum(r.get("ex_total") or 0 for r in rows)
    ex_accuracy = (ex_passed_total / ex_expected_total * 100) if ex_expected_total > 0 else 0
    all_passed_count = sum(1 for r in rows if r.get("all_passed"))
    all_passed_pct = (all_passed_count / total_runs * 100) if total_runs else 0

    print("=" * 70)
    print(f"  📊 AGGREGATE STATS FOR MODE: {args.mode.upper()}")
    print("=" * 70)
    print(f"Total Runs     : {total_runs}")
    print(f"Avg Latency/Run: {avg_latency:.2f}s")
    print(f"Tokens/Run     : {total_tokens/total_runs:.0f} (In: {total_input/total_runs:.0f}, Out: {total_output/total_runs:.0f})")
    print(f"Execution Acc. : {ex_passed_total}/{ex_expected_total} ({ex_accuracy:.1f}%)")
    print(f"Completed Runs : {all_passed_count}/{total_runs} ({all_passed_pct:.1f}%)")
    print("  *(A 'Completed Run' simply means the agent did not timeout and returned a non-empty response)*")
    
    print("\n--- Breakdown by Scenario ---")
    for scen, st in scenario_stats.items():
        r_cnt = st["runs"]
        acc_pct = (st["ex_passed"] / st["ex_total"] * 100) if st["ex_total"] > 0 else 0
        print(f"  {scen}:")
        print(f"    Runs: {r_cnt} | Exec Acc: {st['ex_passed']}/{st['ex_total']} ({acc_pct:.0f}%) | "
              f"Avg Latency: {st['latency']/r_cnt:.1f}s | Avg Tokens: {st['tokens']/r_cnt:.0f}")
    print("=" * 70)

    # 3. Prepare Qualitative Data for LLM Summary
    qualitative_texts = []
    
    # Track scores for averages
    dim_scores = {"analytical_continuity": [], "memory_utilization": [], "reasoning_quality": [], "tool_efficiency": []}

    for idx, r in enumerate(rows, 1):
        qa_raw = r.get("qualitative_analysis")
        if qa_raw:
            try:
                # Standardize format if it's a JSON string
                qa_dict = json.loads(qa_raw) if isinstance(qa_raw, str) else qa_raw
                text = f"\n--- Run {idx} (Scenario: {r.get('scenario')}, Run ID: {r.get('run_id')}) ---\n"
                for k, v in qa_dict.items():
                    if isinstance(v, dict) and "score" in v:
                        score_val = v["score"]
                        if k in dim_scores and isinstance(score_val, (int, float)):
                            dim_scores[k].append(score_val)
                        text += f"- {k.replace('_', ' ').title()}: Score {score_val}/5. {v.get('comment', '')}\n"
                    else:
                        text += f"- {k.replace('_', ' ').title()}: {v}\n"
                qualitative_texts.append(text)
            except Exception:
                qualitative_texts.append(f"\n--- Run {idx} (Scenario: {r.get('scenario')}, Run ID: {r.get('run_id')}) ---\n{qa_raw}")

    # Print average qualitative scores
    have_scores = any(len(v) > 0 for v in dim_scores.values())
    if have_scores:
        print("\n  🧠 QUALITATIVE AVERAGE SCORES (1-5)")
        print("  " + "-" * 40)
        for dim, scores_list in dim_scores.items():
            if scores_list:
                avg_score = sum(scores_list) / len(scores_list)
                print(f"  {dim.replace('_', ' ').title():<22}: {avg_score:.2f}  (n={len(scores_list)})")
        print("=" * 70)

    if not qualitative_texts:
        print("\nNo qualitative analysis found in these runs to summarize.")
        return

    print("\n🤖 Requesting LLM Summary of Qualitative Analyses...")
    
    prompt = (
        f"You are an expert AI behavior evaluator. Below are the qualitative judge assessments "
        f"from {total_runs} benchmarking runs using the memory mode: '{args.mode}'.\n\n"
        f"Please provide a comprehensive and structured summary of the agent's performance. "
        f"Highlight its main strengths, recurring weaknesses/failure modes, how effectively "
        f"it utilized tools and memory, and overall reasoning quality.\n\n"
        f"Summarize findings and takeaways.\n\n"
        f"### QUALITATIVE ASSESSMENTS:\n"
    )

    import random

    result = random.sample(qualitative_texts, 20)

    prompt += "".join(result)

    try:
        # Load environment variables
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            env_path = Path(__file__).parent.parent / ".env"
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        if line.strip() and not line.startswith("#") and "=" in line:
                            k, v = line.strip().split("=", 1)
                            os.environ.setdefault(k, v.strip("'\" "))

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        client = genai.Client(api_key=api_key) if api_key else genai.Client()
        
        resp = client.models.generate_content(model=args.model.strip(), contents=prompt)
        print("\n" + "=" * 70)
        print(f"  📝 LLM QUALITATIVE SUMMARY FOR MODE: {args.mode.upper()}")
        print("=" * 70)
        print(resp.text.strip())
        print("=" * 70)
    except Exception as e:
        print(f"Error calling LLM for summary: {e}")

if __name__ == "__main__":
    main()
