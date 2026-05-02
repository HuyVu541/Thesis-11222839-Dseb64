"""
Evaluation metrics matching thesis §7.4.

4 metrics:
  1. Analytical Continuity Score — does S2 correctly build on S1?
  2. Artifact Reuse Rate         — proportion of relevant prior artifacts referenced
  3. Dependency Resolution Accuracy — on drift scenarios, % of affected artifacts identified
  4. Tool Call Efficiency        — total tool calls per task (lower = better)
"""

from typing import Dict, Any, List
from langchain_core.messages import AIMessage, ToolMessage


def evaluate_scenario_run(
    scenario_id: str,
    mode: str,
    runs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluate a complete scenario run with thesis-aligned metrics.
    
    Args:
        scenario_id: ID of the scenario
        mode: 'none', 'rag', or 'spm'
        runs: List of turn results with 'messages', 'expected_tools', etc.
    """
    total_tokens = 0
    total_latency = 0.0
    all_tool_calls: List[str] = []
    failed_assertions: List[str] = []

    for run in runs:
        total_tokens += run.get("total_tokens", 0)
        total_latency += run.get("latency", 0.0)

        turn_expected = run.get("expected_tools", [])
        turn_forbidden = run.get("forbidden_tools", [])

        # Extract tool calls from AIMessages
        turn_tools = []
        for msg in run.get("messages", []):
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    turn_tools.append(tc["name"].lower())
                    all_tool_calls.append(tc["name"].lower())

        # Check expected tools were called
        for exp in turn_expected:
            if exp not in turn_tools:
                failed_assertions.append(
                    f"Turn {run['turn_id']}: Expected tool '{exp}' not called. Called: {turn_tools}"
                )

        # Check forbidden tools were NOT called
        for forb in turn_forbidden:
            if forb in turn_tools:
                failed_assertions.append(
                    f"Turn {run['turn_id']}: Forbidden tool '{forb}' was called!"
                )

    success = len(failed_assertions) == 0

    # ----------------------------------------------------------------
    # Thesis §7.4 Metrics
    # ----------------------------------------------------------------

    # 1. Analytical Continuity Score
    #    Proportion of turns that met tool expectations (proxy for building on prior work)
    turns_meeting_expectations = sum(
        1 for run in runs
        if not any(
            f"Turn {run['turn_id']}" in fa for fa in failed_assertions
        )
    )
    continuity_score = turns_meeting_expectations / max(len(runs), 1)

    # 2. Artifact Reuse Rate
    #    Proportion of memory-read tools used (list_artifacts, read_artifact, get_dependencies)
    memory_read_tools = {"list_artifacts", "read_artifact", "get_dependencies"}
    memory_reads = sum(1 for t in all_tool_calls if t in memory_read_tools)
    reuse_rate = memory_reads / max(len(all_tool_calls), 1)

    # 3. Dependency Resolution Accuracy
    #    For drift/versioning scenarios: did the agent use get_dependencies or read_artifact to check?
    dep_tools = {"get_dependencies", "read_artifact"}
    dep_calls = sum(1 for t in all_tool_calls if t in dep_tools)
    # This is a simplified proxy; full accuracy requires comparing against reference solution

    # 4. Tool Call Efficiency
    #    Total tool calls (lower = better, controlling for correctness)
    tool_call_count = len(all_tool_calls)

    return {
        "scenario": scenario_id,
        "mode": mode,
        "success": success,
        "total_latency": round(total_latency, 2),
        "total_tokens": total_tokens,
        # Thesis metrics
        "analytical_continuity_score": round(continuity_score, 2),
        "artifact_reuse_rate": round(reuse_rate, 2),
        "dependency_resolution_calls": dep_calls,
        "tool_call_efficiency": tool_call_count,
        "tools_used": all_tool_calls,
        "failed_assertions": failed_assertions,
    }
