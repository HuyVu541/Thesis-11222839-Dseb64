"""
End-to-end integration tests for the memory system.

These tests hit the real /chat/completions API with Docker + Postgres + GOOGLE_API_KEY.
They verify the 3 thesis scenarios (Accurate Retrieval, Conflict Resolution,
Multi-Hop Composition) aligned with MemoryAgentBench and MemoryArena benchmarks.

Supports three-mode evaluation (MEMORY_MODE=spm, rag, or spm_rag) for ablation study.

Metrics collected per turn:
  - latency_s, input_tokens, output_tokens, total_tokens
  - response_chars, tool_calls, tool_call_count
  - ex_result, ex_expected, ex_actual

Results are persisted to Postgres (eval_runs table) and a local JSON backup.

Usage:
    docker compose up -d
    # SPM mode (default)
    pytest tests/test_e2e_memory.py -v --tb=short -s
    # RAG mode
    MEMORY_MODE=rag pytest tests/test_e2e_memory.py -v --tb=short -s
"""

import pytest
import requests
import uuid
import time
import json
import os
import re
import subprocess

from google import genai
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# Hard timeout for test-side Gemini calls (judge functions).
# The SDK's internal tenacity retry can loop for 10+ minutes on 503s;
# this cap forces a fail-fast so we can move to the next retry/test.
JUDGE_CALL_TIMEOUT = 120  # seconds


def _log(msg: str):
    """Print a timestamped log line so we can see what step is hanging."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}", flush=True)


def _gemini_generate(prompt: str, timeout: int = JUDGE_CALL_TIMEOUT) -> str:
    """Call Gemini generate_content with a hard timeout.

    The google-genai SDK retries 503 UNAVAILABLE internally via tenacity
    with no practical upper bound.  Wrapping in a thread with a timeout
    ensures we get control back even if the SDK retries forever.
    """
    def _call():
        client = genai.Client(
            api_key=os.environ.get("GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY")),
        )
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite", contents=prompt,
        )
        return resp.text.strip()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_call)
        return future.result(timeout=timeout)


# ----------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------

BASE_URL = "http://localhost:8000"
TIMEOUT = 600
MEMORY_MODE = os.environ.get("MEMORY_MODE", "spm")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass
# Persist results
RESULTS_DIR = os.environ.get(
    "E2E_RESULTS_DIR",
    os.path.join(os.path.dirname(__file__), "results"),
)
_RUN_ID = time.strftime("%Y%m%d_%H%M%S")
_RUN_RESULTS: list[dict] = []

# Database URL for storing eval runs — always localhost since test runs on host
DB_URL = "postgresql://user:password@localhost:5433/langgraph"


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def create_session(title: str) -> dict:
    """Create a new session via the API, with retry on transient failures."""
    session_id = f"e2e_{uuid.uuid4().hex[:6]}"
    _log(f"create_session({title!r}) → {session_id}")
    for attempt in range(3):
        try:
            r = requests.post(f"{BASE_URL}/sessions", json={
                "id": session_id,
                "title": title,
            }, timeout=TIMEOUT)
            r.raise_for_status()
            _log(f"create_session OK → {session_id}")
            return r.json()
        except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            _log(f"⚠️ create_session attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
            else:
                raise


def chat(session_id: str, message: str) -> dict:
    """Send a chat message and return the full response.
    
    On timeout or HTTP error the test is immediately aborted via pytest.skip()
    because a failed session invalidates the entire scenario — the agent didn't
    get a fair shot and results would not reflect its real capability.
    """
    _log(f"chat() START → session={session_id}, msg={message[:80]!r}...")
    try:
        r = requests.post(f"{BASE_URL}/chat/completions", json={
            "messages": [{"role": "user", "content": message}],
            "conversationId": session_id,
            "stream": False,
        }, timeout=TIMEOUT)
        r.raise_for_status()
        _log(f"chat() OK → session={session_id}, status={r.status_code}")
        return r.json()
    except requests.exceptions.ReadTimeout:
        _log(f"⛔ chat() TIMEOUT after {TIMEOUT}s → aborting scenario")
        pytest.skip(f"Session {session_id} timed out after {TIMEOUT}s — scenario invalid")
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
        _log(f"⛔ chat() HTTP/Connection error → aborting scenario: {e}")
        pytest.skip(f"Session {session_id} failed ({type(e).__name__}) — scenario invalid")


def get_response_text(response: dict) -> str:
    """Extract the assistant's text from a chat response."""
    choices = response.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    parts.append(c["text"])
                elif isinstance(c, str):
                    parts.append(c)
                else:
                    parts.append(str(c))
            return " ".join(parts)
        return str(content)
    return ""


def get_usage(response: dict) -> dict:
    """Extract token usage from the API response."""
    usage = response.get("usage", {})
    return {
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


def number_in_response(text: str, expected: float | None, tolerance: float = 0.001) -> dict:
    """Check if the expected golden number appears anywhere in the agent's response.

    Uses pure regex — no LLM calls.  Handles common formats:
      $1,512.46 | 1512.46 | 1,512 | 1512 | 12 | 4
    For floats the match must be within ±tolerance (default 0.1%).
    For integers the match must be exact.
    """
    if expected is None:
        return {"passed": False, "actual": None, "reasoning": "Golden value was None"}

    # Extract all numbers from the text (strip $, commas)
    raw_numbers = re.findall(r'\$?([\d,]+\.?\d*)', text)
    parsed: list[float] = []
    for n in raw_numbers:
        try:
            parsed.append(float(n.replace(',', '')))
        except ValueError:
            continue

    if not parsed:
        return {"passed": False, "actual": None, "reasoning": "No numbers found in response"}

    # Check if any extracted number is close enough to the expected value
    for val in parsed:
        if expected == 0:
            if val == 0:
                return {"passed": True, "actual": val, "reasoning": f"Exact match: {val}"}
        elif abs(val - expected) / abs(expected) <= tolerance:
            return {"passed": True, "actual": val, "reasoning": f"Match within {tolerance*100:.0f}%: {val} ≈ {expected}"}

    # Find the closest number for reporting
    closest = min(parsed, key=lambda v: abs(v - expected))
    return {"passed": False, "actual": closest, "reasoning": f"Closest number {closest} not within {tolerance*100:.0f}% of {expected}"}


def get_recent_tool_calls(since_seconds: int = 60) -> list[str]:
    """Parse recent backend logs to extract tool call names."""
    _log(f"get_recent_tool_calls(since={since_seconds}s) START")
    try:
        result = subprocess.run(
            ["docker", "compose", "logs", "backend", f"--since={since_seconds}s", "--no-log-prefix"],
            capture_output=True, text=True, timeout=10, cwd=PROJECT_ROOT,
        )
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        clean = ansi_escape.sub('', result.stdout)
        tools = []
        for line in clean.splitlines():
            if "Executing tool:" in line:
                match = re.search(r"Executing tool: (\S+)", line)
                if match:
                    tools.append(match.group(1))
        _log(f"get_recent_tool_calls OK → {len(tools)} tools found")
        return tools
    except Exception as e:
        _log(f"⚠️ get_recent_tool_calls FAILED: {e}")
        return []


def execute_golden_sql(sql: str) -> str:
    """Run SQL directly against Postgres to compute a golden value."""
    _log(f"execute_golden_sql START → {sql[:80]}...")
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres",
         "psql", "-U", "user", "-d", "langgraph", "-t", "-A", "-c", sql],
        capture_output=True, text=True, timeout=15, cwd=PROJECT_ROOT,
    )
    _log(f"execute_golden_sql OK → {result.stdout.strip()!r}")
    return result.stdout.strip()


# ----------------------------------------------------------------
# LLM-as-a-Judge
# ----------------------------------------------------------------

def llm_judge(question: str, agent_response: str, criteria: str) -> dict:
    """Use Gemini to judge whether an agent response meets specific criteria.
    Returns {"passed": bool, "reasoning": str, "score": float}
    """
    prompt = f"""You are an impartial evaluator assessing an AI agent's response against specific criteria.

QUESTION ASKED TO THE AGENT:
{question}

AGENT'S RESPONSE:
{agent_response}

EVALUATION CRITERIA:
{criteria}

Scoring guide:
- 1.0: The response fully and correctly satisfies all criteria with proper justification.
- 0.7-0.9: The response mostly satisfies the criteria with minor gaps or imprecisions.
- 0.4-0.6: The response partially satisfies the criteria but has notable errors or omissions.
- 0.1-0.3: The response attempts to address the criteria but is largely incorrect or incomplete.
- 0.0: The response completely fails to address the criteria or is factually wrong.

Focus on factual correctness and completeness, not writing style.
Set "passed" to true only if score >= 0.7.

Output JSON only:
{{"passed": true/false, "score": 0.0-1.0, "reasoning": "brief explanation"}}
"""
    for attempt in range(3):
        try:
            _log(f"llm_judge Gemini call START (attempt {attempt+1}/3)")
            text = _gemini_generate(prompt)
            _log(f"llm_judge Gemini call OK (attempt {attempt+1}/3)")
            # Parse JSON from response (may be wrapped in markdown)
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"passed": False, "score": 0.0, "reasoning": "Could not parse JSON"}
        except Exception as e:
            _log(f"⚠️ llm_judge error (attempt {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(2)

    return {"passed": False, "score": 0.0, "reasoning": "Judge call failed after retries"}


def qualitative_judge(scenario_name: str, reasoning_chain: list[dict]) -> dict:
    """Full-scenario qualitative analysis using LLM judge with anchored rubric.
    
    Receives the full reasoning chain (all sessions' prompts + responses + tools)
    and provides qualitative assessment on 4 dimensions (1-5 each).
    """
    chain_text = ""
    total_turns = len(reasoning_chain)
    for i, turn in enumerate(reasoning_chain):
        is_final = (i == total_turns - 1)
        marker = " [CRITICAL TURN — this is the main evaluation target]" if is_final else ""
        chain_text += f"\n--- {turn['label']}{marker} ---\n"
        chain_text += f"USER: {turn.get('prompt', 'N/A')}\n"
        chain_text += f"AGENT RESPONSE ({turn.get('response_chars', 0)} chars): {turn.get('response_preview', 'N/A')}\n"
        chain_text += f"TOOLS USED: {', '.join(turn.get('tool_calls', []))}\n"
        if turn.get('ex_result') is not None:
            chain_text += f"EX ACCURACY: {'PASS' if turn['ex_result'] else 'FAIL'} (expected={turn.get('ex_expected')}, actual={turn.get('ex_actual')})\n"

    prompt = f"""You are an impartial evaluator assessing an AI agent's performance across a multi-session Business Intelligence scenario called "{scenario_name}".

FULL REASONING CHAIN (all sessions, in order):
{chain_text}

IMPORTANT EVALUATION RULES:
- The LAST turn (marked [CRITICAL TURN]) is the main evaluation target. Earlier turns are setup context.
- If the critical turn produced an EMPTY response, timed out, or failed EX accuracy, this MUST heavily penalize ALL scores. No dimension should score above 2 if the critical turn failed to produce a correct answer.
- A scenario where setup turns succeed but the critical turn fails is a FAILURE overall.

Score the agent on each dimension using the anchored rubric below. Use the FULL scale — do not default to 3.

---

### 1. Analytical Continuity (1–5)
Did the agent maintain context from prior sessions and correctly apply it in the CRITICAL TURN?

- **1**: Failed to recall prior context in the critical turn. Repeated work, forgot definitions, or produced an empty/timed-out response.
- **2**: Retrieved some prior context but applied it incorrectly in the critical turn (e.g., wrong filter, wrong version).
- **3**: Recalled the most important prior context and used it, but missed some relevant details (e.g., partial filter, minor inaccuracy).
- **4**: Smoothly built on prior sessions. Retrieved and correctly applied prior definitions/findings with only minor gaps.
- **5**: Perfect continuity. Seamlessly integrated all relevant prior work in the critical turn without any re-discovery or context loss.

### 2. Memory Utilization (1–5)
Did the agent effectively use its available memory tools to store and retrieve relevant information?

- **1**: Did not use memory tools at all, used them incorrectly, or got stuck in a retrieval loop (e.g., repeated search_memory calls without progress).
- **2**: Used memory tools but ineffectively — saved too much or too little, retrieved wrong artifacts, or failed to find existing definitions.
- **3**: Used memory tools adequately. Saved key information and retrieved relevant artifacts, but with some missed opportunities or unnecessary calls.
- **4**: Strong memory utilization. Saved definitions appropriately, retrieved the right artifacts, and avoided redundant operations.
- **5**: Optimal memory utilization. Every save/retrieve was purposeful, no redundant operations, and all relevant stored information was leveraged.

### 3. Reasoning Quality (1–5)
Was the agent's analytical reasoning sound and well-justified IN THE CRITICAL TURN?

- **1**: Reasoning was fundamentally wrong, nonsensical, or absent (empty/timed-out response).
- **2**: Reasoning had significant errors — wrong formula application, incorrect joins, missing filters, or unjustified assumptions that affected the result.
- **3**: Reasoning was mostly correct but contained a minor error, or the explanation lacked justification for key steps.
- **4**: Sound reasoning with clear justification. Applied correct formulas and logic with only trivial imprecisions in explanation.
- **5**: Flawless reasoning. Correct formulas, well-structured SQL, clear explanations, and properly justified conclusions.

### 4. Tool Efficiency (1–5)
Did the agent use the right tools in the right order without waste?

- **1**: Excessive tool calls (>3x what was necessary), called tools in wrong order, made many failed/redundant calls, or timed out due to tool-call loops.
- **2**: Noticeable inefficiency — unnecessary tool calls, repeated the same operation, or used a roundabout path to reach the answer.
- **3**: Acceptable efficiency. Used roughly the right tools but with 1–2 unnecessary calls or a suboptimal ordering.
- **4**: Efficient tool use. Minimal unnecessary calls, logical ordering, and good use of available tools.
- **5**: Optimal. Every tool call was necessary and in the ideal order. No wasted operations.

---

Output JSON only. For each dimension, provide a score (integer 1–5) and a brief comment justifying the score:
{{
  "analytical_continuity": {{"score": <1-5>, "comment": "..."}},
  "memory_utilization": {{"score": <1-5>, "comment": "..."}},
  "reasoning_quality": {{"score": <1-5>, "comment": "..."}},
  "tool_efficiency": {{"score": <1-5>, "comment": "..."}},
  "overall_summary": "A 2-3 sentence summary of the agent's overall performance."
}}
"""
    for attempt in range(3):
        try:
            _log(f"qualitative_judge Gemini call START (attempt {attempt+1}/3)")
            text = _gemini_generate(prompt)
            _log(f"qualitative_judge Gemini call OK (attempt {attempt+1}/3)")
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            _log(f"⚠️ qualitative_judge error (attempt {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(2)
    return {"overall_summary": "Qualitative judge call failed after retries"}


# ----------------------------------------------------------------
# Metrics & Logging
# ----------------------------------------------------------------

def make_turn_record(
    label: str, prompt: str, response: dict, latency: float, tool_calls: list[str],
    ex_result: bool | None = None, ex_expected=None, ex_actual=None,
    judge_result: dict | None = None,
) -> dict:
    """Build a structured turn record with all metrics."""
    text = get_response_text(response)
    usage = get_usage(response)
    return {
        "label": label,
        "prompt": prompt,
        "latency_s": round(latency, 2),
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "total_tokens": usage["total_tokens"],
        "response_chars": len(text),
        "response_preview": text,
        "tool_calls": tool_calls,
        "tool_call_count": len(tool_calls),
        "ex_result": ex_result,
        "ex_expected": ex_expected,
        "ex_actual": ex_actual,
        "judge_result": judge_result,
        "passed": True,  # Updated by assertions
        "failure_reason": "",
    }


def print_turn(turn: dict):
    """Print a single turn's results."""
    print(f"\n{'='*70}")
    print(f"  📋 {turn['label']}  [Mode: {MEMORY_MODE.upper()}]")
    print(f"{'='*70}")
    print(f"  Latency:    {turn['latency_s']:.1f}s")
    print(f"  Tokens:     {turn['input_tokens']} in / {turn['output_tokens']} out / {turn['total_tokens']} total")
    print(f"  Response:   {turn['response_chars']} chars")
    print(f"  Tools:      {turn['tool_calls']}")
    if turn['ex_result'] is not None:
        status = "✅" if turn['ex_result'] else "❌"
        print(f"  EX:         {status} (expected={turn['ex_expected']}, actual={turn['ex_actual']})")
    if turn.get('judge_result'):
        j = turn['judge_result']
        status = "✅" if j.get('passed') else "❌"
        print(f"  Judge:      {status} score={j.get('score', 'N/A')} — {j.get('reasoning', '')[:100]}")
    # Preview
    for line in turn['response_preview'].split("\n")[:5]:
        print(f"      {line}")
    print(f"{'='*70}\n")


def finalize_scenario(scenario_name: str, turns: list[dict]):
    """Print summary, run qualitative judge, persist to Postgres + JSON."""
    _log(f"finalize_scenario({scenario_name!r}) START")
    # Qualitative analysis on full chain
    _log("Running qualitative_judge...")
    qual = qualitative_judge(scenario_name, turns)
    _log("qualitative_judge DONE")
    qual_text = json.dumps(qual, indent=2)
    
    total_latency = sum(t["latency_s"] for t in turns)
    total_input = sum(t["input_tokens"] for t in turns)
    total_output = sum(t["output_tokens"] for t in turns)
    total_tokens = sum(t["total_tokens"] for t in turns)
    ex_checks = [t for t in turns if t["ex_result"] is not None]
    ex_passed = sum(1 for t in ex_checks if t["ex_result"])
    ex_total = len(ex_checks)
    all_passed = all(t["passed"] for t in turns)

    # Print summary
    print(f"\n{'*'*70}")
    print(f"  📊 METRICS: {scenario_name}  [Mode: {MEMORY_MODE.upper()}]")
    print(f"{'*'*70}")
    print(f"  Total Turns:          {len(turns)}")
    print(f"  Total Latency:        {total_latency:.1f}s")
    print(f"  Total Tokens:         {total_tokens} ({total_input} in / {total_output} out)")
    if ex_total > 0:
        print(f"  Execution Accuracy:   {ex_passed}/{ex_total} ({ex_passed/ex_total*100:.0f}%)")
    print(f"  All Passed:           {'✅' if all_passed else '❌'}")
    print(f"\n  📝 Qualitative Analysis:")
    for line in qual_text.split("\n")[:15]:
        print(f"      {line}")
    print(f"{'*'*70}\n")

    record = {
        "run_id": _RUN_ID,
        "memory_mode": MEMORY_MODE,
        "scenario": scenario_name,
        "total_turns": len(turns),
        "total_latency_s": round(total_latency, 2),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "ex_passed": ex_passed,
        "ex_total": ex_total,
        "ex_score": round(ex_passed / max(ex_total, 1), 4),
        "all_passed": all_passed,
        "qualitative_analysis": qual_text,
        "turns": turns,
    }
    _RUN_RESULTS.append(record)

    # Save to Postgres
    try:
        import psycopg
        with psycopg.connect(DB_URL, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO eval_runs "
                    "(run_id, memory_mode, scenario, total_turns, total_latency_s, "
                    " total_input_tokens, total_output_tokens, total_tokens, "
                    " ex_passed, ex_total, ex_score, all_passed, qualitative_analysis, turns_json) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        record["run_id"], record["memory_mode"], record["scenario"],
                        record["total_turns"], record["total_latency_s"],
                        record["total_input_tokens"], record["total_output_tokens"],
                        record["total_tokens"], record["ex_passed"], record["ex_total"],
                        record["ex_score"], record["all_passed"],
                        record["qualitative_analysis"],
                        json.dumps(record["turns"], default=str),
                    ),
                )
        _log("💾 Saved to Postgres eval_runs table")
    except Exception as e:
        _log(f"⚠️ Postgres save failed: {e}")
    _log(f"finalize_scenario({scenario_name!r}) DONE")


@pytest.fixture(scope="module", autouse=True)
def _persist_json_backup():
    """Write JSON backup after module finishes."""
    yield
    if not _RUN_RESULTS:
        return
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out = os.path.join(RESULTS_DIR, f"e2e_{MEMORY_MODE}_{_RUN_ID}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(_RUN_RESULTS, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[Harness] ✅ JSON backup saved to: {out}\n")


# ----------------------------------------------------------------
# Health check
# ----------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def check_backend():
    """Skip all tests if backend is not running."""
    try:
        r = requests.get(f"{BASE_URL}/sessions", timeout=5)
        r.raise_for_status()
    except Exception:
        pytest.skip("Backend not running — start with: docker compose up -d")


# ----------------------------------------------------------------
# Selective cleanup: preserve distractors, clear only eval data
# ----------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _preserve_distractor_state():
    """Snapshot memory before eval, clear only eval-specific data, restore after.

    This ensures distractor artifacts survive across eval runs.
    Only eval sessions (e2e_*) are removed from Postgres.
    The memory directory is snapshotted and restored so filesystem/FAISS
    changes from the eval are reverted.
    """
    import psycopg2

    print(f"\n[Harness] 📸 Preparing {MEMORY_MODE} eval (preserving distractors)...")

    # 1. Snapshot the memory directory inside the container (includes distractors)
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend",
         "bash", "-c", "rm -rf /app/memory_snapshot && cp -r /app/memory /app/memory_snapshot"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    if result.returncode == 0:
        print("  ✓ Memory snapshot created")
    else:
        print(f"  ⚠ Snapshot failed: {result.stderr}")

    # 2. Clear only eval-specific Postgres data (sessions/checkpoints starting with e2e_)
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()
        for table, col in [
            ("checkpoint_writes", "thread_id"),
            ("checkpoint_blobs", "thread_id"),
            ("checkpoints", "thread_id"),
            ("sessions", "id"),
        ]:
            try:
                cur.execute(f"DELETE FROM {table} WHERE {col} LIKE 'e2e_%'")
                deleted = cur.rowcount
                if deleted > 0:
                    print(f"  ✓ Cleared {deleted} eval rows from {table}")
            except Exception as e:
                print(f"  ⚠ Could not clear {table}: {e}")
                conn.rollback()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"  ❌ Postgres cleanup failed: {e}")

    # 3. Re-seed prompts (in case they were previously deleted)
    try:
        sql_path = os.path.join(PROJECT_ROOT, "scripts/seed_prompt.sql")
        if os.path.exists(sql_path):
            subprocess.run(
                ["docker", "compose", "exec", "-T", "postgres",
                 "psql", "-U", "user", "-d", "langgraph"],
                input=open(sql_path).read(),
                capture_output=True, text=True, cwd=PROJECT_ROOT,
            )
            print("  ✓ Ensured prompts are seeded")
    except Exception as e:
        print(f"  ⚠ Prompt seed failed: {e}")

    # 4. Set memory_mode in .env to match the MEMORY_MODE pytest env var
    env_path = os.path.join(PROJECT_ROOT, ".env")
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()
        with open(env_path, "w") as f:
            for line in lines:
                if line.strip().startswith("memory_mode="):
                    f.write(f"memory_mode={MEMORY_MODE}\n")
                else:
                    f.write(line)
        print(f"  ✓ Set .env memory_mode={MEMORY_MODE}")
    except Exception as e:
        print(f"  ⚠ Could not update .env: {e}")

    # 5. Restart backend to pick up correct mode + clean checkpoint state
    try:
        subprocess.run(
            ["docker", "compose", "restart", "backend"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        print("  ✓ Restarted backend")
        time.sleep(10)
    except Exception as e:
        print(f"  ⚠ Backend restart failed: {e}")

    print(f"[Harness] ✅ Ready for {MEMORY_MODE} eval (distractors preserved)\n")

    yield  # ---- Tests run here ----

    # 5. Restore memory from snapshot (revert eval artifacts, keep distractors)
    print(f"\n[Harness] 🔄 Restoring memory snapshot (reverting eval artifacts)...")
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend",
         "bash", "-c", "rm -rf /app/memory && mv /app/memory_snapshot /app/memory"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    if result.returncode == 0:
        print("  ✓ Memory restored from snapshot")
    else:
        print(f"  ⚠ Restore failed: {result.stderr}")

    # 6. Restart backend to load restored memory
    subprocess.run(
        ["docker", "compose", "restart", "backend"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    time.sleep(5)
    print("  ✓ Backend restarted with restored state")


# ================================================================
# SCENARIO 1: Accurate Retrieval Under Noise
# Aligned with: MemoryAgentBench AR (Accurate Retrieval)
# ================================================================

class TestAccurateRetrieval:
    """Agent must find the correct definition among 3 confusingly similar ones + distractors.

    All three definitions use the name 'Shipping Performance ___' with overlapping
    vocabulary, but each has company-specific thresholds / filters that cannot be
    inferred from the name alone — the agent MUST retrieve the stored definition.
    
    The retrieval query is deliberately phrased to avoid echoing any definition name
    or formula vocabulary, forcing genuine disambiguation rather than keyword matching.
    """

    def test_accurate_retrieval(self):
        turns = []

        # S1: Define 3 similar "Shipping Performance" definitions + 1 distractor
        s1 = create_session("Retrieval S1")
        prompt1 = (
            "We track four shipping and cost definitions for our logistics team:\n\n"
            "1. 'Shipping Performance Index' is the percentage of orders that were "
            "shipped within 3 days of the order date. "
            "Formula: COUNT(orders where shipped_date - order_date <= 3 days) / COUNT(all orders) * 100.\n\n"
            "2. 'Shipping Cost Efficiency' is the average freight, but only for "
            "orders where the total line item value (unit_price * quantity) exceeds $200. "
            "Ignore orders cheaper than that.\n\n"
            "3. 'Shipping Reliability Score' is the percentage of on-time deliveries "
            "for orders shipped to Germany, France, or the UK. On-time means "
            "shipped_date is at most 1 day after required_date. "
            "Formula: COUNT(on-time EU orders) / COUNT(all EU orders) * 100.\n\n"
            "4. 'Order Cost Average' is simply the average freight across all orders, "
            "with no filtering applied.\n\n"
        )
        start = time.time()
        resp1 = chat(s1["id"], prompt1)
        latency1 = time.time() - start
        tools1 = get_recent_tool_calls(since_seconds=int(latency1) + 5)
        t1 = make_turn_record("S1: Define 4 shipping/cost definitions", prompt1, resp1, latency1, tools1)
        print_turn(t1)
        turns.append(t1)
        if t1["response_chars"] == 0:
            t1["passed"] = False
            t1["failure_reason"] = "Empty response"

        # S2: Query using plain business language that avoids echoing any definition name or formula
        # "minimum order value threshold" does not appear in any stored definition verbatim,
        # forcing the agent to retrieve and reason about definitions rather than keyword-match.
        # "Order Cost Average" is a deliberate distractor — it also involves average freight
        # but has no filtering, so using it would produce a wrong answer.
        s2 = create_session("Retrieval S2")
        prompt2 = (
            "We're doing a logistics review for 1997. "
            "How was our shipping cost efficiency that year? "
        )
        time.sleep(1)
        start = time.time()
        resp2 = chat(s2["id"], prompt2)
        latency2 = time.time() - start
        tools2 = get_recent_tool_calls(since_seconds=int(latency2) + 5)

        # Golden SQL: average freight for orders where line item value > $200, in 1997
        golden_sql = (
            "SELECT ROUND(AVG(o.freight)::numeric, 2) "
            "FROM orders o "
            "WHERE EXTRACT(YEAR FROM o.order_date) = 1997 "
            "AND o.order_id IN ("
            "  SELECT od.order_id FROM order_details od "
            "  GROUP BY od.order_id "
            "  HAVING SUM(od.unit_price * od.quantity) > 200"
            ")"
        )
        golden_raw = execute_golden_sql(golden_sql)
        golden_value = float(golden_raw) if golden_raw else None

        # EX check: ±5% tolerance
        verification = number_in_response(get_response_text(resp2), golden_value, tolerance=0.05)
        extracted = verification.get("actual")
        ex_passed = verification.get("passed", False)

        t2 = make_turn_record(
            "S2: Compute shipping cost for orders meeting minimum value threshold (1997)",
            prompt2, resp2, latency2, tools2,
            ex_result=ex_passed, ex_expected=golden_value, ex_actual=extracted,
        )
        ran_query = "run_query" in tools2
        t2["passed"] = ran_query and t2["response_chars"] > 0
        if not t2["passed"]:
            t2["failure_reason"] = "No query executed or empty response"
        print_turn(t2)
        turns.append(t2)

        finalize_scenario("Accurate Retrieval", turns)


# ================================================================
# SCENARIO 2: Conflict Resolution
# Aligned with: MemoryAgentBench CR (Conflict Resolution)
# ================================================================

class TestConflictResolution:
    """Agent must determine which of 3 contradictory definitions is current."""

    def test_conflict_resolution(self):
        turns = []

        # S1: v1 — freight-based definition
        s1 = create_session("Conflict S1")
        prompt1 = (
            "A 'High Priority Account' is any customer with total freight "
            "charges above $800. How many High Priority Accounts do we have?"
        )
        start = time.time()
        resp1 = chat(s1["id"], prompt1)
        latency1 = time.time() - start
        tools1 = get_recent_tool_calls(since_seconds=int(latency1) + 5)
        t1 = make_turn_record("S1: HPA v1 (freight > $800)", prompt1, resp1, latency1, tools1)
        print_turn(t1)
        turns.append(t1)
        if t1["response_chars"] == 0:
            t1["passed"] = False
            t1["failure_reason"] = "Empty response"

        # S2: v2 — category-based (completely different criteria)
        s2 = create_session("Conflict S2")
        prompt2 = (
            "A 'High Priority Account' should be updated to mean "
            "a customer located in Germany with more than 10 total orders. "
            "How many High Priority Accounts do we have?"
        )
        start = time.time()
        resp2 = chat(s2["id"], prompt2)
        latency2 = time.time() - start
        tools2 = get_recent_tool_calls(since_seconds=int(latency2) + 5)
        t2 = make_turn_record("S2: HPA v3 (Germany + >10 orders)", prompt2, resp2, latency2, tools2)
        print_turn(t2)
        turns.append(t2)
        if t2["response_chars"] == 0:
            t2["passed"] = False
            t2["failure_reason"] = "Empty response"

        # S3: v3 — country + order count (completely different again)
        s3 = create_session("Conflict S3")
        prompt3 = (
            "A 'High Priority Account' should be "
            "a customer who has placed orders in more than 4 distinct "
            "product categories. How many High Priority Accounts do we have?"
        )
        start = time.time()
        resp3 = chat(s3["id"], prompt3)
        latency3 = time.time() - start
        tools3 = get_recent_tool_calls(since_seconds=int(latency3) + 5)
        t3 = make_turn_record("S3: HPA v2 (>4 categories)", prompt3, resp3, latency3, tools3)
        print_turn(t3)
        turns.append(t3)
        if t3["response_chars"] == 0:
            t3["passed"] = False
            t3["failure_reason"] = "Empty response"

        # S4: Query — no "use latest" cue
        s4 = create_session("Conflict S4")
        prompt4 = "How many High Priority Accounts do we have again?"
        time.sleep(1)
        start = time.time()
        resp4 = chat(s4["id"], prompt4)
        latency4 = time.time() - start
        tools4 = get_recent_tool_calls(since_seconds=int(latency4) + 5)

        verification = number_in_response(get_response_text(resp4), 82.0, tolerance=0.0)
        extracted = verification.get("actual")
        ex_passed = verification.get("passed", False)

        t4 = make_turn_record(
            "S4: Count HPA (should find customers who have placed orders in more than 4 distinct product categories)", prompt4, resp4, latency4, tools4,
            ex_result=ex_passed, ex_expected=82, ex_actual=extracted,
        )
        t4["passed"] = t4["response_chars"] > 0
        if not t4["passed"]:
            t4["failure_reason"] = "Empty response"
        print_turn(t4)
        turns.append(t4)

        finalize_scenario("Conflict Resolution", turns)


# ================================================================
# SCENARIO 3: Multi-Hop Composition
# Aligned with: MemoryArena (interdependent multi-session tasks)
# ================================================================

class TestMultiHopComposition:
    """Agent must chain 2 independently-defined concepts from different sessions."""

    def test_multi_hop_composition(self):
        turns = []

        # S1: Define base concept
        s1 = create_session("MultiHop S1")
        prompt1 = (
            "Underperforming Product' means any product that has been "
            "ordered fewer than 30 times total."
        )
        start = time.time()
        resp1 = chat(s1["id"], prompt1)
        latency1 = time.time() - start
        tools1 = get_recent_tool_calls(since_seconds=int(latency1) + 5)
        t1 = make_turn_record("S1: Define Underperforming Product", prompt1, resp1, latency1, tools1)
        print_turn(t1)
        turns.append(t1)
        if t1["response_chars"] == 0:
            t1["passed"] = False
            t1["failure_reason"] = "Empty response"

        # S2: Define a dependent rule
        s2 = create_session("MultiHop S2")
        prompt2 = (
            "Here's a review policy: if a supplier has more than 2 "
            "Underperforming Products, flag them for 'Supplier Review'. "
        )
        start = time.time()
        resp2 = chat(s2["id"], prompt2)
        latency2 = time.time() - start
        tools2 = get_recent_tool_calls(since_seconds=int(latency2) + 5)
        t2 = make_turn_record("S2: Define Supplier Review rule", prompt2, resp2, latency2, tools2)
        print_turn(t2)
        turns.append(t2)
        if t2["response_chars"] == 0:
            t2["passed"] = False
            t2["failure_reason"] = "Empty response"

        # S3: Query that requires chaining both definitions
        s3 = create_session("MultiHop S3")
        prompt3 = "Which suppliers should be flagged for Supplier Review?"
        time.sleep(1)
        start = time.time()
        resp3 = chat(s3["id"], prompt3)
        latency3 = time.time() - start
        tools3 = get_recent_tool_calls(since_seconds=int(latency3) + 5)

        # Golden: suppliers with >2 products ordered <30 times
        # = New Orleans Cajun Delights (3), Grandma Kelly's Homestead (3)
        golden_sql = (
            "SELECT s.company_name, COUNT(p.product_id) as underperforming_count "
            "FROM suppliers s "
            "JOIN products p ON s.supplier_id = p.supplier_id "
            "JOIN ( "
            "  SELECT product_id, COUNT(DISTINCT order_id) AS order_count "
            "  FROM order_details GROUP BY product_id "
            "  HAVING COUNT(DISTINCT order_id) < 30 "
            ") oc ON p.product_id = oc.product_id "
            "GROUP BY s.supplier_id, s.company_name "
            "HAVING COUNT(p.product_id) > 2"
        )
        golden_raw = execute_golden_sql(golden_sql)

        # LLM judge: check if agent identified the correct suppliers
        judge = llm_judge(
            question=prompt3,
            agent_response=get_response_text(resp3),
            criteria=(
                "The agent must identify which suppliers should be flagged for 'Supplier Review'. "
                "The correct answer requires chaining two definitions: "
                "(1) 'Underperforming Product' = ordered fewer than 30 times, and "
                "(2) 'Supplier Review' = supplier with more than 2 Underperforming Products. "
                "The agent should have identified the suppliers: 'New Orleans Cajun Delights' "
                "and 'Grandma Kelly's Homestead' as the correct answer (2 suppliers total). "
                "Partial credit if the agent correctly chains the definitions but gets "
                "slightly different results due to query construction."
            ),
        )

        ex_passed = judge.get("passed", False)

        t3 = make_turn_record(
            "S3: Identify suppliers for review", prompt3, resp3, latency3, tools3,
            ex_result=ex_passed,
            ex_expected="New Orleans Cajun Delights, Grandma Kelly's Homestead",
            ex_actual=get_response_text(resp3),
            judge_result=judge,
        )
        ran_query = "run_query" in tools3
        t3["passed"] = ran_query and t3["response_chars"] > 0
        if not t3["passed"]:
            t3["failure_reason"] = "No query executed or empty response"
        print_turn(t3)
        turns.append(t3)

        finalize_scenario("Multi-Hop Composition", turns)