"""
Evaluation scenarios matching thesis §7.3.

These 4 scenarios are actively adversarial to standard RAG:
  1. Metric Reuse (Distractors) — S1 defines 3 metrics, S2 uniquely queries one
  2. Schema Drift (Hidden Impact) — S1 joins multiple tables, schema renames a key column
  3. Artifact Versioning (Contradictions) — S1 defines rule, S2 adds condition, S3 replaces condition
  4. Cross-Artifact Reasoning (Graph Constraints) — S1 defines Metric, S2 links Insight to Metric, S3 queries Insight strictly

NOTE: Before running these, `test_e2e_memory.py` injects a 50-session synthetic "noise" history to break standard vector lookups.
"""

from typing import List, Optional
from pydantic import BaseModel


class SessionTurn(BaseModel):
    id: str
    prompt: str
    expected_tools: List[str] = []
    forbidden_tools: List[str] = []
    session_id: Optional[str] = None  # If set, use this session; else auto-generate


class Scenario(BaseModel):
    id: str
    name: str
    description: str
    category: str
    sessions: List[SessionTurn]


SCENARIOS = [
    # ----------------------------------------------------------------
    # 1. Metric Reuse (Adversarial Distractors)
    # ----------------------------------------------------------------
    Scenario(
        id="metric_reuse",
        name="Metric Reuse Against Distractor Noise",
        description="Agent defines 3 highly similar metrics. Agent must retrieve the correct one amidst synthetic noise.",
        category="metric_reuse",
        sessions=[
            SessionTurn(
                id="s1_define_distractors",
                session_id="metric_reuse_s1",
                prompt=(
                    "Define and save three separate metrics: "
                    "1. 'Gross Sales' as Quantity * UnitPrice from order_details. "
                    "2. 'Net Sales' as Gross Sales * (1 - Discount). "
                    "3. 'Realized Revenue' as Net Sales, but only where the order was shipped to 'France'. "
                    "Save all three."
                ),
                expected_tools=["save_definition"],
            ),
            SessionTurn(
                id="s2_compute_specific",
                session_id="metric_reuse_s2",
                prompt="Calculate the Realized Revenue for the 'Beverages' category in 1997.",
                expected_tools=["run_query"],
                # Must not rewrite the metric definition
                forbidden_tools=["save_definition"],
            ),
        ],
    ),

    # ----------------------------------------------------------------
    # 2. Schema Drift Detection (Hidden Impact)
    # ----------------------------------------------------------------
    Scenario(
        id="schema_drift",
        name="Cascading Schema Drift",
        description="A metric depends on a specific column. When that column is renamed, the metric is broken. Agent must structurally repair the metric before using it.",
        category="schema_drift",
        sessions=[
            SessionTurn(
                id="s1_define_dependent_metric",
                session_id="drift_s1",
                prompt=(
                    "Define a metric called 'Employee Shipping Efficiency' that divides "
                    "freight by the employee's title_of_courtesy length (just as a synthetic calc). "
                    "Run a query to prove it works, joining orders and employees."
                ),
                expected_tools=["save_definition", "run_query"],
            ),
            # NOTE: Between s1 and s2, the test harness renames 'title_of_courtesy' to 'honorific'
            SessionTurn(
                id="s2_detect_and_repair",
                session_id="drift_s2",
                prompt=(
                    "Compute the Employee Shipping Efficiency for last year. "
                    "Ensure the metric definition is still valid before running."
                ),
                expected_tools=["run_query", "update_artifact"],
            ),
        ],
    ),

    # ----------------------------------------------------------------
    # 3. Artifact Versioning (Contradictory History)
    # ----------------------------------------------------------------
    Scenario(
        id="artifact_versioning",
        name="Artifact Versioning (Contradictory History)",
        description="A metric is revised three times with completely contradictory constraints. The agent must flawlessly use the v3 ruleset without hallucinating v1 or v2.",
        category="versioning",
        sessions=[
            SessionTurn(
                id="s1_define_v1",
                session_id="ver_s1",
                prompt=(
                    "Define 'VIP Customer' as any customer with > 5 total orders. Save it."
                ),
                expected_tools=["save_definition"],
            ),
            SessionTurn(
                id="s2_revise_v2",
                session_id="ver_s2",
                prompt=(
                    "Update the 'VIP Customer' definition to be > 10 orders AND > $5000 in total sales."
                ),
                expected_tools=["update_artifact"],
            ),
            SessionTurn(
                id="s3_revise_v3",
                session_id="ver_s3",
                prompt=(
                    "Forget the $5000 rule. Update 'VIP Customer' to mean > 5 orders AND they are located in London."
                ),
                expected_tools=["update_artifact"],
            ),
            SessionTurn(
                id="s4_query_v3",
                session_id="ver_s4",
                prompt="Count how many VIP Customers we have.",
                expected_tools=["run_query"],
                forbidden_tools=["save_definition", "update_artifact"],
            ),
        ],
    ),

    # ----------------------------------------------------------------
    # 4. Cross-Artifact Reasoning (Hierarchical Graph)
    # ----------------------------------------------------------------
    Scenario(
        id="cross_artifact",
        name="Cross-Artifact Hierarchical Reasoning",
        description="Insight depends on Metric. Agent must traverse from insight to metric down to tables to answer a question.",
        category="cross_artifact",
        sessions=[
            SessionTurn(
                id="s1_define_metric",
                session_id="cross_s1",
                prompt=(
                    "Define a metric 'Late Delivery' as orders where shipped_date > required_date. Save it."
                ),
                expected_tools=["save_definition"],
            ),
            SessionTurn(
                id="s2_define_insight",
                session_id="cross_s2",
                prompt=(
                    "Create an insight called 'Speedy Express Risk': 'If Speedy Express has more than 5 Late Deliveries, we must pause their contract'. Save this insight."
                ),
                expected_tools=["save_insight"],
            ),
            SessionTurn(
                id="s3_traverse",
                session_id="cross_s3",
                prompt=(
                    "Check the Speedy Express Risk insight. Do we need to pause their contract? "
                    "Calculate the latest numbers and evaluate the rule."
                ),
                expected_tools=["run_query"],
            ),
        ],
    ),
]


def get_scenarios() -> List[Scenario]:
    return SCENARIOS
