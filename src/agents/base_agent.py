"""
Base agent — LangGraph orchestration with pluggable tools.

Phase 0: Simplified to remove Langfuse, session_tool_manager, memory_manager,
         memory_registry, and episode tracking.
"""

from typing import List, Dict, Any, Annotated, Optional
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
import operator
from loguru import logger
from ..llms.llm_manager import LLMManager
from ..tools import get_tools
from ..config.settings import settings


class AgentState(Dict):
    messages: Annotated[List[BaseMessage], operator.add]
    # A "clean" chat history that excludes ToolMessage/tool-result steps.
    # Used for building the next-turn LLM prompt so we don't replay the entire
    # tool execution trace forever.
    chat_messages: Annotated[List[BaseMessage], operator.add]


class BaseAgent:
    """
    Base agent class using LangGraph for orchestration.
    """

    def __init__(self, llm_config: Dict[str, Any], tools: Optional[List] = None):
        self.llm_config = llm_config
        self.llm_manager = LLMManager(llm_config)
        
        # Select tool category based on memory mode
        if settings.memory_mode == "rag":
            self.tools = get_tools(["memory_rag"])
        elif settings.memory_mode == "sam":
            self.tools = get_tools(["memory_sam_rag"])
        else:
            self.tools = get_tools(["memory"])

        all_tools = tools or self.tools
        self.tools = all_tools
            
        self._llm = None
        self._llm_with_tools = None
        self._graph = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = self.llm_manager.get_llm()
        return self._llm

    @property
    def llm_with_tools(self):
        if self._llm_with_tools is None:
            self._llm_with_tools = self.llm.bind_tools(self.tools)
        return self._llm_with_tools

    async def get_graph(self):
        """Lazy loader for the compiled graph with async checkpointer."""
        if self._graph is not None:
            return self._graph

        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # from_conn_string returns an async context manager in newer versions
        conn_ctx = AsyncPostgresSaver.from_conn_string(settings.database_url)
        checkpointer = await conn_ctx.__aenter__()
        # Store context so it doesn't get garbage collected
        self._checkpointer_ctx = conn_ctx
        await checkpointer.setup()
        self._graph = self._build_graph(checkpointer)
        return self._graph

    def _build_graph(self, checkpointer):
        graph = StateGraph(AgentState)

        async def call_llm(state: AgentState, config: RunnableConfig):
            # LangGraph stores the full execution trace (including tool calls/results)
            # in `messages`. For next-turn context, we feed the LLM a clean chat
            # history (`chat_messages`) plus only the *most recent* tool results
            # when we're mid tool-loop.
            trace_messages = state["messages"].copy()
            chat_messages = state.get("chat_messages", []).copy()
            if not chat_messages:
                # Backwards compatibility: older checkpoints won't have `chat_messages`.
                # Derive a clean chat view by dropping ToolMessages from the trace.
                chat_messages = [m for m in trace_messages if not isinstance(m, ToolMessage)]

            # Sliding window over chat history only (keeps order; no reordering).
            MAX_CHAT_MESSAGES = 80
            if len(chat_messages) > MAX_CHAT_MESSAGES:
                start_idx = len(chat_messages) - MAX_CHAT_MESSAGES
                
                # ── Safety: never start the window on an orphaned tool-call
                # or tool-result.  Walk forward until we hit a HumanMessage
                # (or system) so the model always sees a valid turn sequence.
                while start_idx < len(chat_messages):
                    m = chat_messages[start_idx]
                    if isinstance(m, HumanMessage):
                        break
                    if getattr(m, "type", "") == "system":
                        break
                    start_idx += 1

                window = chat_messages[start_idx:]

                # Preserve the earliest system message (typically the system prompt)
                # even if it falls outside the chat window.
                first_sys_idx = None
                for i, m in enumerate(chat_messages):
                    if getattr(m, "type", "") == "system":
                        first_sys_idx = i
                        break

                if first_sys_idx is not None and first_sys_idx < start_idx:
                    chat_messages = [chat_messages[first_sys_idx]] + window
                else:
                    chat_messages = window

            messages = chat_messages

            # If the last trace events are tool results, append only those tool
            # results so the model can continue after a tool call without having
            # to replay older tool traces.
            trailing_tool_results: List[ToolMessage] = []
            for m in reversed(trace_messages):
                if isinstance(m, ToolMessage):
                    trailing_tool_results.append(m)
                else:
                    break
            if trailing_tool_results:
                messages = messages + list(reversed(trailing_tool_results))



            response = await self.llm_with_tools.ainvoke(
                messages,
                config=config
            )
            # Always add the assistant message to both:
            # - messages: full trace used by checkpointer/streaming/debugging
            # - chat_messages: compact chat history used for next-turn prompts
            return {"messages": [response], "chat_messages": [response]}

        async def execute_tools(state: AgentState, config: RunnableConfig):
            last_message = state['messages'][-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                tool_results = []
                for tool_call in last_message.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']
                    logger.debug(f"Executing tool: {tool_name}")

                    for t in self.tools:
                        if t.name == tool_name:
                            result = await t.ainvoke(tool_args, config=config)
                            tool_results.append(ToolMessage(
                                content=str(result),
                                tool_call_id=tool_call['id'],
                                name=tool_name
                            ))
                            break
                return {"messages": tool_results}
            return {"messages": []}

        def should_continue(state):
            last_message = state['messages'][-1]
            if isinstance(last_message, AIMessage):
                if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                    return "execute_tools"
            return END

        graph.add_node("call_llm", call_llm)
        graph.add_node("execute_tools", execute_tools)
        graph.add_edge(START, "call_llm")
        graph.add_conditional_edges("call_llm", should_continue)
        graph.add_edge("execute_tools", "call_llm")

        return graph.compile(checkpointer=checkpointer)

    async def arun(self, input_messages: List[BaseMessage], config: Dict[str, Any] = {}):
        """Run the agent with input messages."""
        # Seed both the full trace and the clean chat history with the same
        # initial input (system + latest user message).
        initial_state = AgentState(messages=input_messages, chat_messages=input_messages)
        graph = await self.get_graph()

        # Inject Langfuse callbacks for tracing
        callbacks = self.llm_manager.get_callbacks()
        if callbacks:
            config.setdefault("callbacks", []).extend(callbacks)

        # Safety: limit tool-call iterations to prevent infinite loops
        config.setdefault("recursion_limit", 50)

        result = await graph.ainvoke(initial_state, config=config)
        return result