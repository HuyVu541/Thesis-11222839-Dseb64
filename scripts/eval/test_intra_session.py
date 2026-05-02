import asyncio
from langchain_core.messages import HumanMessage
from src.agents.base_agent import BaseAgent
from src.config.settings import settings
import uuid

async def run_test(enable_scratchpad: bool):
    print(f"\n{'='*50}\nRUNNING WITH SCRATCHPAD: {enable_scratchpad}\n{'='*50}")
    
    agent = BaseAgent(
        llm_config={"provider": "google-generativeai", "model": settings.llm_model},
        enable_scratchpad=enable_scratchpad
    )
    
    messages = []
    session_id = f"eval_intra_session_{uuid.uuid4().hex[:8]}"
    
    prompts = [
        "Please define a new metric called 'Premium Freight' as any order where freight > 100. Save it.",
        "Now define 'Late Shipments' as any order where shipped_date > required_date. Save it.",
        "Run a query to get the top 25 Premium Freight orders. Output all the raw rows in a markdown table so I can inspect them.",
        "Run a query to get the top 25 Late Shipments. Output all the raw rows in a markdown table.",
        "Run a query to list 25 customers and their contact titles. Output all the raw rows.",
        "Now, without using the list_artifacts tool, tell me the exact formulas for the two metrics we defined earlier. Then execute a single query combining them: count how many orders are BOTH Premium Freight and Late Shipments.",
    ]
    
    for i, p in enumerate(prompts):
        print(f"\n[Turn {i+1}] User: {p}")
        messages.append(HumanMessage(content=p))
        
        config = {
            "metadata": {"session_id": session_id},
            "configurable": {"thread_id": session_id}
        }
        result = await agent.arun(messages, config)
        
        # arun returns the full state
        # Find the last AIMessage content
        for msg in reversed(result["messages"]):
            if msg.type == "ai" and msg.content:
                content = msg.content
                if isinstance(content, list):
                    text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and "text" in item]
                    content = " ".join(text_parts)
                print(f"Agent: {content.strip()[:300]}...\n")
                break
                
        # Count tool calls in this turn
        new_messages = result["messages"][len(messages):]
        tool_calls = sum(1 for m in new_messages if m.type == "tool")
        print(f"--> Tools used in this turn: {tool_calls}")
        
        # update messages for the next turn
        messages = result["messages"]

if __name__ == "__main__":
    async def main():
        # First without scratchpad
        await run_test(enable_scratchpad=False)
        # Then with scratchpad
        await run_test(enable_scratchpad=True)
        
    asyncio.run(main())
