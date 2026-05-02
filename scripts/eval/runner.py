"""
Evaluation Harness Runner.

Executes scenarios across different memory backends: None, RAG, SPM.
Tracks metrics and saves results.
"""

import sys
import os
import time
import json
import uuid
from typing import Dict, Any, List
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from src.config.settings import settings
from src.agents.base_agent import BaseAgent
from src.api.db import db_manager
from src.api.models import SessionCreate
from scripts.eval.scenarios import get_scenarios, Scenario
from scripts.eval.metrics import evaluate_scenario_run

# --- Mocking Tool Loaders for different modes ---

def run_scenario(scenario: Scenario, mode: str) -> Dict[str, Any]:
    """Run a single scenario in the specified mode."""
    print(f"\n[{mode.upper()}] Running Scenario: {scenario.name}")
    
    # 1. Setup Backend Mode
    # We create a new DB and ArtifactStore per scenario to ensure isolation
    test_id = f"eval_{scenario.id}_{mode}_{int(time.time())}"
    
    # Use temporary stores
    settings.memory_base_path = f"/tmp/ai_memory_eval/{test_id}"
    os.makedirs(settings.memory_base_path, exist_ok=True)
    
    # Initialize Agent with specific tools based on mode
    from src.tools.registry import registry
    registry._tools = {} # Clear registry
    registry._categories = {}
    
    # Load base tools (math, basic)
    import src.tools.basic_tools
    
    if mode == "spm":
        import src.tools.memory.memory_tools
    elif mode == "rag":
        import src.tools.memory.rag_tools
        from src.memory.rag_baseline import RAGBaseline
        from src.tools.memory.rag_tools import set_rag_store
        
        # We might skip if no Gemini key
        if not os.environ.get("GOOGLE_API_KEY"):
            return {"scenario": scenario.id, "mode": mode, "error": "No GOOGLE_API_KEY"}
            
        try:
            rag = RAGBaseline(base_path=str(Path(settings.memory_base_path) / "rag"))
            set_rag_store(rag)
        except Exception as e:
            return {"scenario": scenario.id, "mode": mode, "error": f"RAG init failed: {e}"}
    elif mode == "none":
        # Don't load any memory tools, just basic and database execution
        import src.tools.database.sql_executor # For direct query tool if we want to mock it, or just use basic
        # We need a basic run_query tool for the agent if it has no memory
        from langchain_core.tools import tool
        @registry.register("memory_none")
        @tool
        def run_query(sql: str) -> str:
            """Execute a SQL query against the project database."""
            from src.tools.database.sql_executor import execute_sql
            return execute_sql(sql)["formatted"]
            
    agent = BaseAgent(llm_config=settings.llm_config)
    
    results = []
    
    for turn in scenario.sessions:
        print(f"  -> Turn: {turn.id}")
        session_id = turn.session_id or f"{test_id}_{turn.id}"
        
        # We simulate creating a session in the DB
        db_manager.create_session(SessionCreate(id=session_id, title=turn.id))
        
        # Configure graph checkpointing
        config = {
            "configurable": {"thread_id": session_id},
            "metadata": {"session_id": session_id}
        }
        
        messages = [
            SystemMessage(content="You are a helpful BI agent. Give concise answers."),
            HumanMessage(content=turn.prompt)
        ]
        
        # Run agent
        start_time = time.time()
        
        import asyncio
        try:
            # We must use asyncio.run since we are in a script
            result_state = asyncio.run(agent.arun(messages, config=config))
            latency = time.time() - start_time
            
            # Extract real token counts from AIMessage.usage_metadata
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0
            for m in result_state['messages']:
                if isinstance(m, AIMessage) and hasattr(m, 'usage_metadata') and m.usage_metadata:
                    meta = m.usage_metadata
                    input_tokens += meta.get('input_tokens', 0)
                    output_tokens += meta.get('output_tokens', 0)
                    total_tokens += meta.get('total_tokens', 0)
            
            # Fallback to estimation if no metadata available
            if total_tokens == 0:
                full_text = " ".join([m.content for m in result_state['messages'] if isinstance(m.content, str)])
                total_tokens = len(full_text) // 4
            
            results.append({
                "turn_id": turn.id,
                "messages": result_state["messages"][len(messages):], # Only new messages
                "expected_tools": turn.expected_tools,
                "forbidden_tools": turn.forbidden_tools,
                "latency": latency,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            })
            
        except Exception as e:
            print(f"    ERROR: {e}")
            results.append({
                "turn_id": turn.id,
                "error": str(e),
                "messages": [],
                "expected_tools": turn.expected_tools,
                "forbidden_tools": turn.forbidden_tools,
                "latency": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            })
            
    # Evaluate
    eval_result = evaluate_scenario_run(scenario.id, mode, results)
    print(f"    Result: {'PASS' if eval_result['success'] else 'FAIL'} ({eval_result['total_latency']}s)")
    if not eval_result["success"]:
        for f in eval_result["failed_assertions"]:
            print(f"      - {f}")
            
    return eval_result

def main():
    modes = ["none", "rag", "spm"]
    scenarios = get_scenarios()
    
    all_results = []
    
    for s in scenarios:
        for m in modes:
            res = run_scenario(s, m)
            all_results.append(res)
            
    # Save results
    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    
    out_file = out_dir / f"eval_run_{int(time.time())}.json"
    with open(out_file, "w") as f:
        json.dump(all_results, f, indent=2)
        
    print(f"\nEvaluation complete. Results saved to {out_file}")

if __name__ == "__main__":
    main()
