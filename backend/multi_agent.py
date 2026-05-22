import json
import os
import re
import asyncio
from typing import AsyncGenerator, TypedDict, Any

from langgraph.graph import StateGraph, START, END

from agent_prompts import (
    COORDINATOR_PROMPT,
    PROFILE_PROMPT,
    DOCUMENT_PROMPT,
    QUIZ_PROMPT,
    MINDMAP_PROMPT,
    VIDEO_SCRIPT_PROMPT,
    CODE_EXAMPLE_PROMPT,
    READING_PROMPT,
    PATH_PROMPT,
    TUTOR_PROMPT,
    ASSESSMENT_PROMPT,
    ANTI_HALLUCINATION_PROMPT,
)
from openai_client import chat_complete, stream_chat

# ── Constants ───────────────────────────────────────────────────────

RESOURCE_PROMPTS = {
    "document": DOCUMENT_PROMPT, "quiz": QUIZ_PROMPT,
    "mindmap": MINDMAP_PROMPT, "video": VIDEO_SCRIPT_PROMPT,
    "code": CODE_EXAMPLE_PROMPT, "reading": READING_PROMPT,
}

RESOURCE_LABELS = {
    "document": "课程讲解文档", "quiz": "配套练习题",
    "mindmap": "知识点思维导图", "video": "教学视频脚本",
    "code": "代码实操案例", "reading": "拓展阅读材料",
    "path": "学习路径规划", "tutor": "答疑辅导",
    "assessment": "学习效果评估",
}

DIMENSION_KEYS = [
    "major_background", "knowledge_base", "cognitive_style",
    "learning_goals", "weak_points", "schedule_preference", "content_preference",
]

DIMENSION_ZH_MAP = {
    "专业背景": "major_background", "知识基础": "knowledge_base",
    "认知风格": "cognitive_style", "学习目标": "learning_goals",
    "知识短板": "weak_points", "学习节奏": "schedule_preference",
    "内容偏好": "content_preference",
}

_pipeline_profile_cache: dict = {}

def get_pipeline_profile_updates() -> dict:
    result = dict(_pipeline_profile_cache)
    _pipeline_profile_cache.clear()
    return result


# ── State ───────────────────────────────────────────────────────────

class AgentState(TypedDict):
    intents: list[str]
    target_topic: str | None
    target_resource_types: list[str]
    user_content: str
    history: list[dict]
    profile_dict: dict
    coordinator_response: str

# Module-level queue (set before graph run, accessed by nodes via closure or global)
_queue: asyncio.Queue | None = None


# ── Helpers ─────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try: return json.loads(m.group())
        except json.JSONDecodeError: pass
    return {}

def _profile_context_to_dict(profile_context: str) -> dict:
    result: dict = {}
    for line in profile_context.split("\n"):
        line = line.strip().lstrip("- ")
        for zh, key in DIMENSION_ZH_MAP.items():
            if line.startswith(f"{zh}："):
                val = line[len(zh) + 1:].strip()
                if val: result[key] = val
    return result

def _build_agent_input(agent_type: str, topic: str, profile_dict: dict, user_content: str, history: list[dict]) -> str:
    profile_input = {k: (profile_dict.get(k) or None) for k in DIMENSION_KEYS}
    if agent_type in RESOURCE_PROMPTS:
        return json.dumps({"student_profile": profile_input, "topic": topic}, ensure_ascii=False)
    return ""

def _parse_agent_output(raw: str) -> str:
    j = _extract_json(raw)
    if j.get("resource") and isinstance(j["resource"], dict):
        return j["resource"].get("content", "")
    if "learning_path" in j: return j["learning_path"]
    if "answer" in j: return j["answer"]
    if "assessment" in j: return j["assessment"]
    return raw

async def _run_anti_hallucination(content: str, agent_type: str, topic: str) -> str:
    if not content or len(content.strip()) < 50: return content
    print(f"[anti_hallucination] Reviewing {agent_type}, input_len={len(content)}", flush=True)
    review_input = json.dumps({
        "resource": {"resource_id": f"{agent_type}_001", "resource_type": agent_type, "topic": topic, "content": content}
    }, ensure_ascii=False)
    try:
        reviewed_raw = await chat_complete([
            {"role": "system", "content": ANTI_HALLUCINATION_PROMPT},
            {"role": "user", "content": f"请审核：\n\n{review_input}"},
        ])
        j = _extract_json(reviewed_raw)
        if j.get("resource") and isinstance(j["resource"], dict):
            result = j["resource"].get("content", content)
            print(f"[anti_hallucination] Done, output_len={len(result)}", flush=True)
            return result
    except Exception as e:
        print(f"[anti_hallucination] Error: {e}", flush=True)
    return content


# ── Router ──────────────────────────────────────────────────────────

async def detect_intent(user_message: str, history: list[dict], profile_context: str) -> dict:
    print(f"[router] detect_intent called, user_message='{user_message[:60]}...'", flush=True)
    profile_dict = _profile_context_to_dict(profile_context)
    profile_json = {k: (profile_dict.get(k) or "null") for k in DIMENSION_KEYS}
    coordinator_input = json.dumps({
        "conversation_history": history[-12:],
        "student_profile": profile_json,
    }, ensure_ascii=False)
    try:
        result = await chat_complete([
            {"role": "system", "content": COORDINATOR_PROMPT},
            {"role": "user", "content": f"请分析以下输入，判断用户意图：\n\n{coordinator_input}"},
        ])
        j = _extract_json(result)
        if j:
            j.setdefault("intents", ["chat"]); j.setdefault("target_topic", None)
            j.setdefault("target_resource_types", ["document", "mindmap", "quiz"])
            # ----- TODO输出即使响应的位置(后期可能需要完善一下，避免出现白屏太长) ------
            j.setdefault("response", "你好！我是智学通，有什么学习问题可以帮你？")
            print(f"[router] result: intents={j.get('intents')}, topic={j.get('target_topic')}, types={j.get('target_resource_types')}", flush=True)
            return j
    except Exception as e:
        print(f"[router] Error: {e}", flush=True)
    return {"intents": ["chat"], "target_topic": None, "target_resource_types": ["document", "mindmap", "quiz"], "response": "你好！有什么可以帮你的？"}


# ── Profile Node ────────────────────────────────────────────────────

async def _profile_node(state: AgentState) -> AgentState:
    if "profile" not in state["intents"]: return state
    print(f"[profile_node] Starting, history_len={len(state['history'])}", flush=True)
    q = _queue
    profile_input = {k: (state["profile_dict"].get(k) or None) for k in DIMENSION_KEYS}
    payload = json.dumps({"conversation_history": state["history"][-12:], "student_profile": profile_input}, ensure_ascii=False)
    if len(state["history"]) >= 2:
        try:
            result = await chat_complete([
                {"role": "system", "content": PROFILE_PROMPT},
                {"role": "user", "content": f"请分析：\n\n{payload}"},
            ])
            j = _extract_json(result)
            if j.get("student_profile") and isinstance(j["student_profile"], dict):
                new_dims = {k: v for k, v in j["student_profile"].items() if v and v != "null"}
                if new_dims:
                    _pipeline_profile_cache.clear(); _pipeline_profile_cache.update(new_dims)
                    for k, v in new_dims.items(): state["profile_dict"][k] = v
                    print(f"[profile_node] Updated dimensions: {list(new_dims.keys())}", flush=True)
                else:
                    print(f"[profile_node] No new dimensions extracted", flush=True)
        except Exception as e:
            print(f"[profile_node] Error: {e}", flush=True)

    # Stream formatted profile as Markdown
    zh_labels = {
        "major_background": "🎓 专业背景", "knowledge_base": "📚 知识基础",
        "cognitive_style": "🧠 认知风格", "learning_goals": "🎯 学习目标",
        "weak_points": "🔧 知识短板", "schedule_preference": "⏱️ 学习节奏",
        "content_preference": "📋 内容偏好",
    }
    lines = ["# 📋 我的学习档案\n"]
    has_any = False
    for key, label in zh_labels.items():
        val = state["profile_dict"].get(key, "")
        if val and val.strip():
            lines.append(f"## {label}\n{val.strip()}\n")
            has_any = True
    if not has_any:
        lines.append("> 学习档案尚未建立。继续对话，系统将自动分析并构建你的学习画像。\n")
        lines.append("> 多聊一些关于你学习的内容（专业、课程、遇到的困难等），档案会逐渐丰富。")
    markdown = "\n".join(lines)
    for char in markdown:
        await q.put({"type": "delta", "delta": char})

    return state


# ── Path / Tutor / Assessment Nodes ─────────────────────────────────

async def _path_node(state: AgentState) -> AgentState:
    if "path" not in state["intents"]:
        return state
    q = _queue
    topic = state["target_topic"] or state["user_content"][:60]
    print(f"[path_node] Starting, topic={topic}", flush=True)
    await q.put({"type": "status", "status": "正在生成学习路径规划...", "resource_type": "path"})

    payload = json.dumps({
        "student_profile": {k: (state["profile_dict"].get(k) or None) for k in DIMENSION_KEYS},
        "conversation_history": state["history"][-12:]
    }, ensure_ascii=False)

    print(f"[path_node] Payload length: {len(payload)}", flush=True)
    print(f"[path_node] Calling stream_chat...", flush=True)

    full = ""
    token_count = 0
    try:
        async for token in stream_chat([
            {"role": "system", "content": PATH_PROMPT},
            {"role": "user", "content": payload},
        ]):
            full += token
            token_count += 1
            await q.put({"type": "hidden_delta", "delta": token})

        print(f"[path_node] Stream finished. Total tokens: {token_count}, full length: {len(full)}", flush=True)

    except Exception as e:
        print(f"[path_node] LLM error: {e}", flush=True)
        import traceback
        traceback.print_exc()

    content = _parse_agent_output(full)
    print(f"[path_node] raw_len={len(full)}, parsed_len={len(content)}", flush=True)

    if content and len(content.strip()) >= 20:
        header = "\n## 🗺️ 学习路径规划\n\n"
        for char in header:
            await q.put({"type": "delta", "delta": char})
        for char in content:
            await q.put({"type": "delta", "delta": char})
        await q.put({"type": "save_resource", "rtype": "path", "topic": topic, "content": content, "reviewed": False})
    else:
        print(f"[path_node] WARNING: Content too short or empty, not saving", flush=True)

    return state



async def _tutor_node(state: AgentState) -> AgentState:
    if "tutor" not in state["intents"]: return state
    q = _queue
    topic = state["target_topic"] or state["user_content"][:40]
    print(f"[tutor_node] Starting, topic={topic}", flush=True)
    await q.put({"type": "status", "status": "正在解答...", "resource_type": "tutor"})
    payload = json.dumps({"student_profile": {k: (state["profile_dict"].get(k) or None) for k in DIMENSION_KEYS}, "conversation_history": state["history"][-12:], "user_question": state["user_content"]}, ensure_ascii=False)
    full = ""
    try:
        async for token in stream_chat([
            {"role": "system", "content": TUTOR_PROMPT},
            {"role": "user", "content": payload},
        ]):
            full += token
            await q.put({"type": "hidden_delta", "delta": token})
    except Exception as e:
        print(f"[tutor_node] LLM error: {e}", flush=True)
        import traceback; traceback.print_exc()
    content = _parse_agent_output(full)
    print(f"[tutor_node] raw_len={len(full)}, parsed_len={len(content)}", flush=True)
    if content and len(content.strip()) >= 10:
        header = "\n## 💡 答疑辅导\n\n"
        for char in header:
            await q.put({"type": "delta", "delta": char})
        for char in content:
            await q.put({"type": "delta", "delta": char})
        await q.put({"type": "save_resource", "rtype": "tutor", "topic": topic, "content": content, "reviewed": False})
    return state

async def _assessment_node(state: AgentState) -> AgentState:
    if "assessment" not in state["intents"]: return state
    q = _queue
    topic = state["target_topic"] or state["user_content"][:40]
    print(f"[assessment_node] Starting, topic={topic}", flush=True)
    await q.put({"type": "status", "status": "正在生成评估...", "resource_type": "assessment"})
    payload = json.dumps({"student_profile": {k: (state["profile_dict"].get(k) or None) for k in DIMENSION_KEYS}, "conversation_history": state["history"][-12:]}, ensure_ascii=False)
    full = ""
    try:
        async for token in stream_chat([
            {"role": "system", "content": ASSESSMENT_PROMPT},
            {"role": "user", "content": payload},
        ]):
            full += token
            await q.put({"type": "hidden_delta", "delta": token})
    except Exception as e:
        print(f"[assessment_node] LLM error: {e}", flush=True)
        import traceback; traceback.print_exc()
    content = _parse_agent_output(full)
    print(f"[assessment_node] raw_len={len(full)}, parsed_len={len(content)}", flush=True)
    if content and len(content.strip()) >= 20:
        header = "\n## 📊 学习效果评估\n\n"
        for char in header:
            await q.put({"type": "delta", "delta": char})
        for char in content:
            await q.put({"type": "delta", "delta": char})
        await q.put({"type": "save_resource", "rtype": "assessment", "topic": topic, "content": content, "reviewed": False})
    return state


# ── Response Node ───────────────────────────────────────────────────

async def _send_response_node(state: AgentState) -> AgentState:
    q = _queue
    resp = state["coordinator_response"]
    print(f"[graph] send_response: '{resp[:60]}...' ({len(resp)} chars), intents={state['intents']}", flush=True)
    for char in resp:
        await q.put({"type": "delta", "delta": char})
    return state


# ── Resource Router (asyncio.gather for parallel agents) ──────────

async def _resource_router_node(state: AgentState) -> AgentState:
    """Run all matching resource agents in parallel via asyncio.gather."""
    if "resource" not in state["intents"]:
        print(f"[resource_router] Skipped — 'resource' not in intents {state['intents']}", flush=True)
        return state

    rtypes = [r for r in state["target_resource_types"] if r in RESOURCE_PROMPTS]
    if not rtypes:
        return state

    topic = state["target_topic"] or state["user_content"][:60]
    print(f"[resource_router] Running {len(rtypes)} agents: {rtypes}, topic={topic}", flush=True)

    SECTION_ICONS = {
        "document": "📖", "quiz": "✏️", "mindmap": "🧠",
        "video": "🎬", "code": "💻", "reading": "📚",
    }

    async def _run_one(rtype: str):
        prompt = RESOURCE_PROMPTS[rtype]
        label = RESOURCE_LABELS.get(rtype, rtype)
        icon = SECTION_ICONS.get(rtype, "📄")
        await _queue.put({"type": "status", "status": f"正在生成{label}...", "resource_type": rtype})

        json_input = _build_agent_input(rtype, topic, state["profile_dict"], state["user_content"], state["history"])
        full = ""
        is_quiz = (rtype == "quiz")
        # All resource agents produce JSON-wrapped output — stream as hidden
        # so raw JSON never renders in chat.
        try:
            async for token in stream_chat([
                {"role": "system", "content": prompt},
                {"role": "user", "content": json_input},
            ]):
                full += token
                await _queue.put({"type": "hidden_delta", "delta": token})
        except Exception as e:
            print(f"[resource:{rtype}] LLM error: {e}", flush=True)
            import traceback;
            traceback.print_exc()
            return

        content = _parse_agent_output(full)

        import json
        if isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False, indent=2)
        elif not isinstance(content, str):
            content = str(content)

        print(f"[resource:{rtype}] raw_len={len(full)}, parsed_len={len(content)}", flush=True)

        if is_quiz:
            if full and len(full.strip()) >= 20:
                await _queue.put(
                    {"type": "save_quiz", "rtype": rtype, "topic": topic, "content": full})
                print(f"[resource:{rtype}] Quiz raw saved for exercise extraction", flush=True)
        elif content and len(content.strip()) >= 50:
            print(f"[resource:{rtype}] Running anti-hallucination review...", flush=True)
            reviewed = await _run_anti_hallucination(content, rtype, topic)
            # Wrap mindmap content so the frontend renders it as an
            # interactive SVG mind map with PNG download.
            if rtype == "mindmap":
                reviewed = f"<!--MINDMAP-->\n{reviewed}\n<!--ENDMINDMAP-->"
            # Stream clean reviewed content into chat with a section header
            header = f"\n## {icon} {label}\n\n"
            for char in header:
                await _queue.put({"type": "delta", "delta": char})
            for char in reviewed:
                await _queue.put({"type": "delta", "delta": char})
            await _queue.put(
                {"type": "save_resource", "rtype": rtype, "topic": topic, "content": reviewed, "reviewed": True})
            print(f"[resource:{rtype}] Saved, reviewed_len={len(reviewed)}", flush=True)
        else:
            print(f"[resource:{rtype}] Skipped save — content too short or empty", flush=True)

    await asyncio.gather(*[_run_one(r) for r in rtypes])
    return state


# ── Routing functions ───────────────────────────────────────────────

def _route_after_response(state: AgentState) -> str:
    """Chain: profile → resource → path → tutor → assessment → finalize"""
    intents = state["intents"]
    if "profile" in intents: dest = "profile"
    elif "resource" in intents: dest = "resource_router"
    elif "path" in intents: dest = "path"
    elif "tutor" in intents: dest = "tutor"
    elif "assessment" in intents: dest = "assessment"
    else: dest = "finalize"
    print(f"[graph] route after send_response → {dest} (intents={intents})", flush=True)
    return dest

def _route_after_profile(state: AgentState) -> str:
    intents = state["intents"]
    if "resource" in intents: dest = "resource_router"
    elif "path" in intents: dest = "path"
    elif "tutor" in intents: dest = "tutor"
    elif "assessment" in intents: dest = "assessment"
    else: dest = "finalize"
    print(f"[graph] route after profile → {dest} (intents={intents})", flush=True)
    return dest

def _route_after_resource(state: AgentState) -> str:
    intents = state["intents"]
    if "path" in intents: dest = "path"
    elif "tutor" in intents: dest = "tutor"
    elif "assessment" in intents: dest = "assessment"
    else: dest = "finalize"
    print(f"[graph] route after resource → {dest} (intents={intents})", flush=True)
    return dest

def _route_after_path(state: AgentState) -> str:
    intents = state["intents"]
    if "tutor" in intents: dest = "tutor"
    elif "assessment" in intents: dest = "assessment"
    else: dest = "finalize"
    print(f"[graph] route after path → {dest} (intents={intents})", flush=True)
    return dest

def _route_after_tutor(state: AgentState) -> str:
    intents = state["intents"]
    if "assessment" in intents: dest = "assessment"
    else: dest = "finalize"
    print(f"[graph] route after tutor → {dest} (intents={intents})", flush=True)
    return dest


# ── Finalize Node ───────────────────────────────────────────────────

async def _finalize_node(state: AgentState) -> AgentState:
    print(f"[graph] finalize — sending done signal", flush=True)
    await _queue.put({"type": "done"})
    return state


# ── Build Graph ─────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("send_response", _send_response_node)
    graph.add_node("profile", _profile_node)
    graph.add_node("resource_router", _resource_router_node)
    graph.add_node("path", _path_node)
    graph.add_node("tutor", _tutor_node)
    graph.add_node("assessment", _assessment_node)
    graph.add_node("finalize", _finalize_node)

    graph.add_edge(START, "send_response")

    graph.add_conditional_edges("send_response", _route_after_response, {
        "profile": "profile", "resource_router": "resource_router",
        "path": "path", "tutor": "tutor", "assessment": "assessment", "finalize": "finalize",
    })
    graph.add_conditional_edges("profile", _route_after_profile, {
        "resource_router": "resource_router",
        "path": "path", "tutor": "tutor", "assessment": "assessment", "finalize": "finalize",
    })
    graph.add_conditional_edges("resource_router", _route_after_resource, {
        "path": "path", "tutor": "tutor", "assessment": "assessment", "finalize": "finalize",
    })
    graph.add_conditional_edges("path", _route_after_path, {
        "tutor": "tutor", "assessment": "assessment", "finalize": "finalize",
    })
    graph.add_conditional_edges("tutor", _route_after_tutor, {
        "assessment": "assessment", "finalize": "finalize",
    })
    graph.add_edge("assessment", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()

_graph = _build_graph()


# ── Main Pipeline ───────────────────────────────────────────────────

async def run_agent_pipeline(
    history: list[dict],
    user_content: str,
    profile_context: str,
    intents: list[str],
    target_topic: str | None,
    target_resource_types: list[str],
    coordinator_response: str,
) -> AsyncGenerator[str, None]:
    """Run the LangGraph agent pipeline with streaming output."""
    global _queue
    print(f"[pipeline] Starting, intents={intents}, topic={target_topic}, resource_types={target_resource_types}", flush=True)
    profile_dict = _profile_context_to_dict(profile_context)
    _queue = asyncio.Queue()

    initial_state: AgentState = {
        "intents": intents,
        "target_topic": target_topic,
        "target_resource_types": target_resource_types,
        "user_content": user_content,
        "history": history,
        "profile_dict": profile_dict,
        "coordinator_response": coordinator_response,
    }

    # Run graph in background task
    async def _run_graph():
        try:
            print(f"[graph] Starting with intents: {intents}", flush=True)
            await _graph.ainvoke(initial_state)
            print(f"[graph] Completed successfully", flush=True)
        except Exception as e:
            print(f"[graph] Error: {e}", flush=True)
            import traceback; traceback.print_exc()
            await _queue.put({"type": "done"})

    graph_task = asyncio.create_task(_run_graph())

    # Read from queue and yield SSE events
    resource_count = 0
    quiz_count = 0
    save_events: list[dict] = []
    quiz_events: list[dict] = []

    while True:
        try:
            item = await asyncio.wait_for(_queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            if graph_task.done():
                break
            continue

        if item["type"] == "done":
            break
        elif item["type"] == "save_resource":
            save_events.append(item)
            resource_count += 1
        elif item["type"] == "save_quiz":
            quiz_events.append(item)
            quiz_count += 1
        elif item["type"] == "delta":
            yield f"data: {json.dumps({'delta': item['delta']})}\n\n"
        elif item["type"] == "hidden_delta":
            # Hidden from chat UI — still yield so frontend knows generation
            # is alive, but marked hidden so it won't be rendered.
            yield f"data: {json.dumps({'hidden': True, 'delta': item['delta']})}\n\n"
        elif item["type"] == "status":
            yield f"data: {json.dumps({'type': 'status', 'status': item['status']})}\n\n"
            total = len([i for i in intents if i != 'chat'])
            yield f"data: {json.dumps({'type': 'progress', 'current': resource_count + quiz_count + 1, 'total': total, 'label': item['status'], 'resource_type': item.get('resource_type', '')})}\n\n"

    await graph_task
    _queue = None

    # Emit resource save events (quiz events handled separately)
    for ev in save_events:
        yield f"data: {json.dumps({'type': '_save', 'rtype': ev['rtype'], 'topic': ev['topic'], 'content': ev['content'], 'reviewed': ev['reviewed']})}\n\n"

    # Emit quiz save events (exercises extracted inline by main.py)
    for ev in quiz_events:
        yield f"data: {json.dumps({'type': '_save_quiz', 'rtype': ev['rtype'], 'topic': ev['topic'], 'content': ev['content']})}\n\n"

    print(f"[pipeline] Done — {resource_count} resources, {quiz_count} quizzes", flush=True)
    yield f"data: {json.dumps({'type': 'complete', 'total': resource_count, 'quiz_total': quiz_count})}\n\n"
