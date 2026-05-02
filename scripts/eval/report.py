"""
Report Generator for Memory Evaluation.

Reads test result JSON and generates a markdown report
comparing No Memory, RAG Baseline, and SPM (Structured Persistent Memory).
"""

import json
import argparse
from pathlib import Path

def generate_report(json_path: str):
    """Generate a markdown report from the evaluation results."""
    with open(json_path, "r") as f:
        data = json.load(f)
        
    # Group by scenario
    scenarios = {}
    for res in data:
        sid = res["scenario"]
        mode = res["mode"]
        if sid not in scenarios:
            scenarios[sid] = {}
        scenarios[sid][mode] = res

    # Generate Markdown Table
    md = [
        "# AI Memory Backend Evaluation Report",
        "",
        "This report compares the performance of three memory architectures on various multi-session BI tasks.",
        "",
        "## Overall Comparison",
        "",
        "| Scenario | Mode | Pass | Latency (s) | Tokens | Continuity | Reuse Rate | Dep Calls | Tool Calls |",
        "|----------|------|------|-------------|--------|------------|------------|-----------|------------|"
    ]
    
    for sid, modes in scenarios.items():
        for mode in ["none", "rag", "spm"]:
            if mode not in modes:
                continue
                
            res = modes[mode]
            success = "✅" if res.get("success", False) else "❌"
            latency = f"{res.get('total_latency', 0):.2f}"
            tokens = res.get("total_tokens", 0)
            cont = res.get("analytical_continuity_score", "—")
            reuse = res.get("artifact_reuse_rate", "—")
            dep = res.get("dependency_resolution_calls", 0)
            tools = res.get("tool_call_efficiency", 0)
            
            md.append(f"| {sid} | **{mode.upper()}** | {success} | {latency} | {tokens} | {cont} | {reuse} | {dep} | {tools} |")
            
    md.append("")
    md.append("## Detailed Failures")
    md.append("")
    
    for res in data:
        if not res.get("success", False) and "error" not in res:
            md.append(f"### {res['scenario']} ({res['mode'].upper()})")
            for f in res.get("failed_assertions", []):
                md.append(f"- {f}")
            md.append("")
        elif "error" in res:
            md.append(f"### {res['scenario']} ({res['mode'].upper()})")
            md.append(f"- **Error:** {res['error']}")
            md.append("")
            
    out_file = Path(json_path).with_suffix(".md")
    with open(out_file, "w") as f:
        f.write("\n".join(md))
        
    print(f"Report written to: {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Eval Report")
    parser.add_argument("file", help="Path to evaluation JSON results")
    args = parser.parse_args()
    generate_report(args.file)
