"""
FastAPI routes for the BI Agent backend.

Simplified for single-project scope — no users, no data sources,
no session tool config, no memory mode switching.
"""

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from ..agents.base_agent import BaseAgent
from ..config.settings import settings
from .models import SessionCreate, SessionResponse
from .db import db_manager
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
import uuid
import json
import time
from loguru import logger

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

# Initialize FastAPI app
app = FastAPI(title="BI Agent API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatCompletionRequest(BaseModel):
    messages: List[Dict[str, Any]]
    model: str = "gemini-2.5-flash"
    stream: Optional[bool] = False
    conversationId: Optional[str] = None

    class Config:
        extra = "allow"


agent = BaseAgent(llm_config=settings.llm_config)


# ===== Session Endpoints =====

@app.get("/sessions", response_model=List[SessionResponse])
async def get_sessions():
    return db_manager.get_sessions()


@app.post("/sessions", response_model=SessionResponse)
async def create_session(session: SessionCreate):
    return db_manager.create_session(session)


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    success = db_manager.delete_session(session_id)
    if success:
        return {"success": True, "message": f"Session {session_id} deleted"}
    raise HTTPException(status_code=404, detail="Session not found")


@app.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Get all messages for a session from LangGraph checkpointer."""
    try:
        config = {"configurable": {"thread_id": session_id}}
        graph = await agent.get_graph()
        try:
            state = await graph.aget_state(config)
        except Exception:
            return {"messages": []}

        if not state or not state.values:
            return {"messages": []}

        messages = state.values.get("messages", [])
        formatted = []
        for msg in messages:
            # Skip system prompts and raw tool outputs from the UI
            if isinstance(msg, ToolMessage) or isinstance(msg, SystemMessage):
                continue

            content = ""
            if hasattr(msg, 'content') and msg.content:
                if isinstance(msg.content, str):
                    content = msg.content
                elif isinstance(msg.content, list):
                    content = ''.join(
                        item.get('text', '') if isinstance(item, dict) else str(item)
                        for item in msg.content
                    )

            msg_dict = {
                "role": "user" if isinstance(msg, HumanMessage) else "assistant",
                "content": content
            }
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                msg_dict["toolCalls"] = [
                    {"id": tc.get('id'), "name": tc.get('name'),
                     "args": tc.get('args', {}), "status": "completed"}
                    for tc in msg.tool_calls
                ]
            formatted.append(msg_dict)

        return {"messages": formatted}
    except Exception as e:
        logger.exception(f"Error retrieving messages for session {session_id}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Chat Completions =====

@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    try:
        thread_id = request.conversationId or str(uuid.uuid4())

        # Ensure session exists in the DB
        last_user_msg = next((msg for msg in reversed(request.messages) if msg['role'] == 'user'), None)
        title = last_user_msg['content'][:50] if last_user_msg else "New Chat"
        db_manager.create_session(SessionCreate(id=thread_id, title=title))

        config = {
            "configurable": {"thread_id": thread_id},
            "metadata": {"session_id": thread_id}
        }

        # Check if thread is new
        graph = await agent.get_graph()
        try:
            state = await graph.aget_state(config)
            is_new = not state or not state.values or not state.values.get("messages")
        except Exception:
            is_new = True

        new_messages = []
        
        # Inject user system prompt ONCE per thread
        if is_new:
            logger.info(f"✨ New session started: {thread_id}")
            prompt = db_manager.get_prompt_for_mode(settings.memory_mode)
            prompt_content = prompt["content"] if prompt else "You are a helpful BI agent."
            new_messages.append(SystemMessage(content=prompt_content))

        # --- Auto-retrieve: inject relevant context from FAISS ---
        # For RAG and SAM+RAG modes, automatically search FAISS with the
        # user's message and inject top-k results as context. Both modes
        # get identical auto-retrieval treatment; the only difference is
        # FAISS content (RAG: conversation chunks; SAM+RAG: conversation
        # chunks + structured SAM artifacts).
        if last_user_msg and settings.memory_mode in ("rag", "sam"):
            try:
                if settings.memory_mode == "rag":
                    from ..tools.memory.rag_tools import _get_rag
                    rag = _get_rag()
                else:
                    from ..tools.memory.memory_tools import _get_store
                    store = _get_store()
                    rag = store.rag if store.rag else None

                if rag:
                    retrieved = rag.search(last_user_msg['content'], k=5)
                    if retrieved:
                        ctx_lines = ["[AUTOMATICALLY RETRIEVED CONTEXT — may or may not be relevant]\n"]
                        for r in retrieved:
                            ctx_lines.append(f"  [{r.get('type','?')}] {r.get('id','?')}: {r.get('content','')[:300]}\n")
                        auto_ctx = "\n".join(ctx_lines)
                        new_messages.append(SystemMessage(content=auto_ctx))
                        logger.info(f"📥 Auto-retrieved {len(retrieved)} chunks for context")
            except Exception as e:
                logger.warning(f"Auto-retrieve failed: {e}")

        # Append exactly the new user message (not the history, since LangGraph keeps it)
        if last_user_msg:
            new_messages.append(HumanMessage(content=last_user_msg['content']))

        if not new_messages:
            raise HTTPException(status_code=400, detail="No new messages provided")

        if request.stream:
            return StreamingResponse(
                _stream_response(new_messages, config),
                media_type="text/event-stream"
            )

        # Non-streaming
        result = await agent.arun(new_messages, config=config)

        def _extract_text(content) -> str:
            """Safely extract text from AIMessage.content (str, list, or empty)."""
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        parts.append(c.get("text", ""))
                    elif isinstance(c, str):
                        parts.append(c)
                return " ".join(parts)
            return ""

        # Prefer the last AIMessage with actual text content;
        # fall back to the absolute last AIMessage (tool-call-only)
        last_ai = None
        last_ai_any = None
        for msg in reversed(result['messages']):
            if isinstance(msg, AIMessage):
                if last_ai_any is None:
                    last_ai_any = msg
                if _extract_text(msg.content).strip():
                    last_ai = msg
                    break
        if last_ai is None:
            last_ai = last_ai_any
        if not last_ai:
            raise HTTPException(status_code=500, detail="No AI response")

        # Accumulate token usage from all AIMessages in this run
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        for msg in result['messages']:
            if isinstance(msg, AIMessage) and hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                meta = msg.usage_metadata
                prompt_tokens += meta.get('input_tokens', 0)
                completion_tokens += meta.get('output_tokens', 0)
                total_tokens += meta.get('total_tokens', 0)

        # Auto-embed conversation turns for RAG and SAM+RAG modes.
        # Both modes get conversation turns auto-embedded into FAISS,
        # ensuring identical base content. SAM+RAG additionally has
        # structured SAM artifacts synced via ArtifactStore.
        if settings.memory_mode in ("rag", "sam"):
            from ..memory.models import GenericContext

            if settings.memory_mode == "rag":
                from ..tools.memory.rag_tools import _get_rag
                rag = _get_rag()
            else:
                from ..tools.memory.memory_tools import _get_store
                store = _get_store()
                rag = store.rag if store.rag else None

            if rag:
                rag.write_artifact(GenericContext(
                    id=f"ctx_{uuid.uuid4().hex[:8]}",
                    text=last_user_msg['content'],
                    tags={"session_id": thread_id},
                    session_id=thread_id
                ))

                rag.write_artifact(GenericContext(
                    id=f"ctx_{uuid.uuid4().hex[:8]}",
                    text=_extract_text(last_ai.content),
                    tags={"session_id": thread_id},
                    session_id=thread_id
                ))

        return JSONResponse(content={
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": last_ai.content},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        })

    except Exception as e:
        logger.exception("Error in chat_completions")
        raise HTTPException(status_code=500, detail=str(e))


async def _stream_response(new_messages, config):
    """SSE streaming generator for chat completions."""
    response_id = f"chatcmpl-{uuid.uuid4()}"
    graph = await agent.get_graph()

    try:
        async for chunk in graph.astream(
            {"messages": new_messages}, config=config, stream_mode="messages"
        ):
            if isinstance(chunk, tuple) and len(chunk) == 2:
                message = chunk[0]

                if isinstance(message, AIMessage):
                    if hasattr(message, 'tool_calls') and message.tool_calls:
                        for tool_call in message.tool_calls:
                            event = {
                                "id": response_id,
                                "choices": [{"delta": {"tool_calls": [{
                                    "index": 0,
                                    "function": {
                                        "name": tool_call.get('name'),
                                        "arguments": json.dumps(tool_call.get('args', {}))
                                    }
                                }]}}]
                            }
                            yield f"data: {json.dumps(event)}\n\n"

                    if message.content:
                        content_str = message.content if isinstance(message.content, str) else str(message.content)
                        if content_str:
                            event = {"id": response_id, "choices": [{"delta": {"content": content_str}}]}
                            yield f"data: {json.dumps(event)}\n\n"

                elif isinstance(message, ToolMessage):
                    event = {
                        "id": response_id, "type": "tool_result",
                        "tool_name": message.name, "tool_id": message.tool_call_id,
                        "result": message.content
                    }
                    yield f"data: {json.dumps(event)}\n\n"

    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        event = {"id": response_id, "choices": [{"delta": {"content": f"\n\n❌ Error: {e}"}}]}
        yield f"data: {json.dumps(event)}\n\n"

    yield f"data: {json.dumps({'id': response_id, 'choices': [{'finish_reason': 'stop'}]})}\n\n"
    yield "data: [DONE]\n\n"


# ===== Prompt Management =====

@app.get("/config/prompts")
async def list_prompts():
    prompts = db_manager.get_prompts()
    active = db_manager.get_prompt_for_mode(settings.memory_mode)
    return {"prompts": prompts, "active_id": active["id"] if active else ""}


@app.get("/config/prompts/{prompt_id}")
async def get_prompt(prompt_id: str):
    prompt = db_manager.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")
    return prompt


@app.post("/config/prompts/active")
async def set_active_prompt(request: dict = Body(...)):
    prompt_id = request.get("prompt_id")
    if not prompt_id:
        raise HTTPException(status_code=400, detail="prompt_id is required")
    if not db_manager.set_active_prompt(prompt_id):
        raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")
    return {"active_id": prompt_id, "status": "updated"}


@app.get("/config/system-prompt")
async def get_system_prompt():
    logger.info(f"Getting system prompt for memory mode: {settings.memory_mode}")
    prompt = db_manager.get_prompt_for_mode(settings.memory_mode)
    if not prompt:
        raise HTTPException(status_code=404, detail="No prompts configured")
    return {"prompt": prompt["content"], "prompt_id": prompt["id"],
            "name": prompt["name"], "version": prompt.get("version")}


@app.put("/config/system-prompt")
async def update_system_prompt(prompt: str = Body(..., embed=True)):
    active = db_manager.get_active_prompt()
    if not active:
        raise HTTPException(status_code=404, detail="No active prompt found")
    result = db_manager.update_prompt_content(active["id"], prompt)
    return {"status": "updated", "prompt_id": active["id"]}


# ===== Schema Management =====

@app.post("/schemas/sync")
async def sync_database_schema():
    """Sync the Postgres schema into the ArtifactStore."""
    from ..tools.database.schema_introspector import sync_schema
    from ..tools.memory.memory_tools import _get_store
    
    store = _get_store()
    result = sync_schema(store)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
        
    return result