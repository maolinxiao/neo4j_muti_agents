import json
import re
from time import perf_counter
from typing import Any, Generator

import httpx

from app.core.config import settings
from app.services.qa_answer_templates import stream_output_instructions


class MiniMaxClient:
    def __init__(self) -> None:
        self.client = httpx.Client(
            base_url=settings.minimax_api_base,
            timeout=60.0,
            trust_env=False,
            follow_redirects=True,
        )

    def health_check(self) -> bool:
        return bool(settings.minimax_api_key)

    def local_analyze_question(self, question: str) -> dict[str, Any]:
        return self._fallback_analysis(question)

    def analyze_question(self, question: str, entity_candidates: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
        fallback = self._fallback_analysis(question)
        if not settings.minimax_api_key:
            return fallback, 0

        candidate_payload = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "entity_type": item.get("entity_type"),
                "score": item.get("score"),
            }
            for item in entity_candidates[:12]
        ]
        payload = {
            "model": settings.minimax_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是药食同源问答系统里的问题解析器。"
                        "你只负责理解用户问题，不负责给出医学建议。"
                        "请严格输出 JSON，对象字段必须包含 question_type, needs_multi_entity, asked_aspects, summary, search_terms。"
                        "question_type 只能从 herb_efficacy, disease_relation, formula_relation, formula_replacement, constitution_recommendation, product_recommendation, entity_explanation 中选择。"
                        "asked_aspects 必须是数组，可从 efficacy, ingredient, target, formula, disease, symptom, usage, caution 中选择。"
                        "search_terms 必须是数组，优先给出最适合知识图谱检索的实体词，可同时包含中文词和英文疾病/药材标准名。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "entity_candidates": candidate_payload,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0.2,
            "max_completion_tokens": 500,
            "reasoning_split": False,
        }
        started = perf_counter()
        try:
            response = self.client.post(
                "/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.minimax_api_key}",
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json",
                },
                json=payload,
            )
            elapsed_ms = int((perf_counter() - started) * 1000)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = self._parse_json_text(content)
            return {
                "question_type": parsed.get("question_type") or fallback["question_type"],
                "needs_multi_entity": bool(parsed.get("needs_multi_entity", fallback["needs_multi_entity"])),
                "asked_aspects": parsed.get("asked_aspects") or fallback["asked_aspects"],
                "summary": parsed.get("summary") or fallback["summary"],
                "search_terms": parsed.get("search_terms") or fallback["search_terms"],
            }, elapsed_ms
        except Exception:
            elapsed_ms = int((perf_counter() - started) * 1000)
            return fallback, elapsed_ms

    def generate_answer(self, context: dict[str, Any], system_prompt: str) -> tuple[dict[str, Any], int]:
        if not settings.minimax_api_key:
            return self._fallback_answer(context), 0

        payload = {
            "model": settings.minimax_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ],
            "temperature": settings.default_temperature,
            "max_completion_tokens": max(settings.default_max_completion_tokens, 2400),
            "reasoning_split": True,
        }
        started = perf_counter()
        try:
            response = self.client.post(
                "/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.minimax_api_key}",
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json",
                },
                json=payload,
            )
            elapsed_ms = int((perf_counter() - started) * 1000)
            response.raise_for_status()
            data = response.json()
            message = data["choices"][0]["message"]
            content = message.get("content", "")
            think_content = self._extract_reasoning_text(message) or self._extract_think_content(content)
            parsed = self._parse_json_text(self._remove_think_blocks(content))
            parsed["_reasoning_details"] = message.get("reasoning_details")
            parsed["_think_content"] = think_content
            parsed["_fallback"] = False
            return parsed, elapsed_ms
        except Exception as exc:
            elapsed_ms = int((perf_counter() - started) * 1000)
            return self._fallback_answer(context, f"MiniMax 调用失败：{exc}"), elapsed_ms

    def generate_answer_stream(
        self, context: dict[str, Any], system_prompt: str
    ) -> Generator[dict[str, str], None, None]:
        """Stream the conclusion text from MiniMax, yielding {event, text} dicts.

        event='think' for chain-of-thought blocks, event='token' for answer text.
        """
        question_type = str(context.get("question_type") or "entity_explanation")
        stream_system = f"{system_prompt.strip()}\n{stream_output_instructions(question_type)}"
        stream_context = dict(context)
        stream_context.setdefault("answer_rules", [])
        stream_context["answer_rules"] = list(stream_context["answer_rules"]) + [
            "直接输出自然语言回答，不要输出 JSON、字段名或提示词说明。",
        ]
        payload = {
            "model": settings.minimax_model,
            "messages": [
                {"role": "system", "content": stream_system},
                {"role": "user", "content": json.dumps(stream_context, ensure_ascii=False)},
            ],
            "temperature": settings.default_temperature,
            "max_completion_tokens": max(settings.default_max_completion_tokens, 2400),
            "reasoning_split": True,
            "stream": True,
        }
        fallback = self._fallback_answer(context)
        fallback_text = fallback.get("conclusion", "")
        if not settings.minimax_api_key:
            yield {"event": "token", "text": fallback_text}
            return

        try:
            with self.client.stream(
                "POST",
                "/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.minimax_api_key}",
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "text/event-stream",
                },
                json=payload,
            ) as response:
                response.raise_for_status()
                in_think = False
                text_buffer = ""
                for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            reasoning_text = self._extract_reasoning_text(delta)
                            if reasoning_text:
                                yield {"event": "think", "text": reasoning_text}
                            text = delta.get("content", "")
                            if not text:
                                continue

                            text_buffer += text
                            events, text_buffer, in_think = self._drain_think_stream_buffer(text_buffer, in_think)
                            for event in events:
                                yield event
                    except json.JSONDecodeError:
                        continue
                events, text_buffer, in_think = self._drain_think_stream_buffer(text_buffer, in_think, force=True)
                for event in events:
                    yield event
        except Exception:
            yield {"event": "token", "text": fallback_text}

    def rewrite_answer(
        self,
        *,
        question: str,
        question_type: str,
        draft_conclusion: str,
        evidence_summary: str,
        selected_entities: list[dict[str, Any]],
        graph_metrics: dict[str, Any],
    ) -> tuple[str, int]:
        if not settings.minimax_api_key:
            return draft_conclusion, 0

        payload = {
            "model": settings.minimax_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是药食同源知识问答系统中的答案润色助手。"
                        "你只能基于已经给出的草稿答案和证据摘要改写 conclusion，不能新增图谱外事实。"
                        "你的目标是让 conclusion 更像对用户问题的解释性回答，而不是证据条目的复述。"
                        "改写后的 conclusion 必须："
                        "1. 先直接回答用户问题；"
                        "2. 再解释这些证据意味着什么、能推到什么层面；"
                        "3. 最后点明当前图谱还缺什么关键信息。"
                        "必须保留草稿中的【】小标题分段结构，可调整措辞但不得删除或合并分段。"
                        "不要输出证据编号、关系类型名、节点 id、括号里的“证据：...”样式。"
                        "不要重复 evidence_summary 的原句。"
                        "请严格输出 JSON，对象字段只包含 conclusion。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "question_type": question_type,
                            "draft_conclusion": draft_conclusion,
                            "evidence_summary": evidence_summary,
                            "selected_entities": selected_entities[:6],
                            "graph_metrics": graph_metrics,
                            "rewrite_requirements": [
                                "不要把 evidence_summary 直接改写成近义句",
                                "不要以“根据当前知识图谱”开头",
                                "至少写 4 句话",
                                "先回答问题，再解释证据意味着什么，最后说明当前证据边界",
                                "至少使用一次“这说明”“这表明”或“因此”这类解释性表达",
                                "不要补充草稿答案和证据摘要里没有出现过的药理学、营养学或临床常识",
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": min(settings.default_temperature + 0.1, 0.5),
            "max_completion_tokens": 500,
            "reasoning_split": False,
        }
        started = perf_counter()
        try:
            response = self.client.post(
                "/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.minimax_api_key}",
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json",
                },
                json=payload,
            )
            elapsed_ms = int((perf_counter() - started) * 1000)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            rewritten = self._extract_rewritten_conclusion(content)
            return (rewritten or draft_conclusion), elapsed_ms
        except Exception:
            elapsed_ms = int((perf_counter() - started) * 1000)
            return draft_conclusion, elapsed_ms

    def generate_structured_output(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        fallback: dict[str, Any],
        output_schema: dict[str, Any] | None = None,
        required_keys: list[str] | None = None,
        agent_key: str | None = None,
        temperature: float | None = None,
        max_completion_tokens: int = 900,
    ) -> tuple[dict[str, Any], int]:
        if not settings.minimax_api_key:
            return fallback, 0

        resolved_required_keys = self._resolve_required_keys(output_schema, fallback, required_keys)
        guarded_prompt = self._compose_structured_system_prompt(
            system_prompt=system_prompt,
            output_schema=output_schema,
            required_keys=resolved_required_keys,
            agent_key=agent_key,
        )

        request_payload = {
            "model": settings.minimax_model,
            "messages": [
                {"role": "system", "content": guarded_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "temperature": settings.default_temperature if temperature is None else temperature,
            "max_completion_tokens": max_completion_tokens,
            "reasoning_split": False,
        }
        started = perf_counter()
        try:
            response = self.client.post(
                "/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.minimax_api_key}",
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json",
                },
                json=request_payload,
            )
            elapsed_ms = int((perf_counter() - started) * 1000)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = self._parse_json_text(content)
            if isinstance(parsed, dict) and self._matches_expected_shape(parsed, resolved_required_keys):
                return self._normalize_structured_output(parsed, fallback, resolved_required_keys), elapsed_ms
            return fallback, elapsed_ms
        except Exception:
            elapsed_ms = int((perf_counter() - started) * 1000)
            return fallback, elapsed_ms

    def build_rnd_brief(self, question: str) -> dict[str, Any]:
        brief = {
            "goal": question.strip(),
            "constraints": [],
            "dosage_form": "",
            "target_population": "",
            "timeline": "",
            "budget": "",
            "compliance_scope": "药食同源目录内成分",
        }
        text = question.strip()
        lower_text = text.lower()
        dosage_forms = ["固体饮料", "咀嚼片", "代用茶", "颗粒", "胶囊", "口服液", "压片糖果", "饮品"]
        for form in dosage_forms:
            if form in text:
                brief["dosage_form"] = form
                break
        population_tokens = ["儿童", "老人", "女性", "男性", "白领", "学生", "健身人群", "孕妇", "术后人群"]
        for token in population_tokens:
            if token in text:
                brief["target_population"] = token
                break
        if "药食同源" in text:
            brief["constraints"].append("仅使用药食同源目录成分")
        if "预算有限" in text or "成本敏感" in text:
            brief["budget"] = "预算有限"
        if "gb" in lower_text or "国标" in text or "标准" in text:
            brief["constraints"].append("符合相关食品法规与国标要求")
        timeline_match = re.search(r"(\d+)\s*个?月", text)
        if timeline_match:
            brief["timeline"] = f"{timeline_match.group(1)}个月内"
        budget_match = re.search(r"预算[^\d]{0,6}(\d+(?:\.\d+)?)\s*(元|万元|万|w|W)", text)
        if budget_match:
            brief["budget"] = f"{budget_match.group(1)}{budget_match.group(2)}"
        return brief

    @staticmethod
    def _extract_think_content(text: str) -> str:
        """Extract <think>...</think> reasoning content from model output."""
        matches = re.findall(r"<think\b[^>]*>([\s\S]*?)(?:</think>|$)", text, flags=re.I)
        return "\n\n".join(match.strip() for match in matches if match.strip())

    @staticmethod
    def _extract_reasoning_text(payload: dict[str, Any]) -> str:
        """Extract MiniMax reasoning text from reasoning_split=True response shapes."""
        parts: list[str] = []
        reasoning_content = payload.get("reasoning_content")
        if isinstance(reasoning_content, str) and reasoning_content:
            return reasoning_content
        reasoning_details = payload.get("reasoning_details")
        if isinstance(reasoning_details, list):
            for item in reasoning_details:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        parts.append(text)
                elif isinstance(item, str) and item:
                    parts.append(item)
        return "".join(parts)

    @staticmethod
    def _remove_think_blocks(text: str) -> str:
        """Remove model reasoning tags before JSON/text parsing."""
        return re.sub(r"<think\b[^>]*>[\s\S]*?(?:</think>|$)", "", text, flags=re.I).strip()

    @staticmethod
    def _drain_think_stream_buffer(
        buffer: str,
        in_think: bool,
        force: bool = False,
    ) -> tuple[list[dict[str, str]], str, bool]:
        """Split streamed text into visible answer tokens and think tokens across chunk boundaries."""
        open_tag = "<think>"
        close_tag = "</think>"
        events: list[dict[str, str]] = []

        while buffer:
            lower_buffer = buffer.lower()
            if in_think:
                close_index = lower_buffer.find(close_tag)
                if close_index != -1:
                    if close_index > 0:
                        events.append({"event": "think", "text": buffer[:close_index]})
                    buffer = buffer[close_index + len(close_tag):]
                    in_think = False
                    continue

                answer_index = MiniMaxClient._find_stream_answer_boundary(buffer)
                if answer_index != -1:
                    if answer_index > 0:
                        events.append({"event": "think", "text": buffer[:answer_index]})
                    buffer = buffer[answer_index:]
                    in_think = False
                    continue

                if force:
                    events.append({"event": "think", "text": buffer})
                    buffer = ""
                    break

                keep_len = max(len(close_tag) - 1, 80)
                safe_len = max(0, len(buffer) - keep_len)
                if safe_len == 0:
                    break
                events.append({"event": "think", "text": buffer[:safe_len]})
                buffer = buffer[safe_len:]
                break

            if MiniMaxClient._looks_like_stream_reasoning_start(buffer):
                in_think = True
                continue

            open_index = lower_buffer.find(open_tag)
            close_index = lower_buffer.find(close_tag)
            if close_index != -1 and (open_index == -1 or close_index < open_index):
                if close_index > 0:
                    events.append({"event": "token", "text": buffer[:close_index]})
                buffer = buffer[close_index + len(close_tag):]
                continue

            if open_index != -1:
                if open_index > 0:
                    events.append({"event": "token", "text": buffer[:open_index]})
                buffer = buffer[open_index + len(open_tag):]
                in_think = True
                continue

            if force:
                events.append({"event": "token", "text": buffer})
                buffer = ""
                break

            keep_len = 0
            max_candidate_len = min(len(open_tag) - 1, len(buffer))
            for candidate_len in range(1, max_candidate_len + 1):
                if open_tag.startswith(lower_buffer[-candidate_len:]):
                    keep_len = candidate_len
            safe_len = len(buffer) - keep_len
            if safe_len > 0:
                events.append({"event": "token", "text": buffer[:safe_len]})
                buffer = buffer[safe_len:]
            break

        return events, buffer, in_think

    @staticmethod
    def _looks_like_stream_reasoning_start(text: str) -> bool:
        stripped = text.lstrip()
        reasoning_starts = ("用户", "让我", "我需要", "我先", "从图谱中", "从知识图谱中")
        return any(stripped.startswith(marker) for marker in reasoning_starts)

    @staticmethod
    def _find_stream_answer_boundary(text: str) -> int:
        markers = [
            "\n\n【核心结论】",
            "\n\n【图谱依据】",
            "\n\n根据您",
            "\n\n根据知识图谱",
            "\n\n针对您",
            "\n\n对于您",
            "\n\n基于当前",
        ]
        indexes = [text.find(marker) for marker in markers]
        indexes = [index for index in indexes if index != -1]
        return min(indexes) + 2 if indexes else -1

    def _extract_rewritten_conclusion(self, text: str) -> str | None:
        parsed = self._parse_json_text(text)
        if isinstance(parsed, dict):
            candidate = parsed.get("conclusion")
            if isinstance(candidate, str):
                cleaned = candidate.strip()
                if cleaned and "<think>" not in cleaned.lower():
                    return cleaned

        match = re.search(r'"conclusion"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.S)
        if not match:
            return None
        raw_value = match.group(1)
        try:
            cleaned = json.loads(f'"{raw_value}"').strip()
        except json.JSONDecodeError:
            cleaned = raw_value.replace('\\"', '"').replace("\\n", "\n").strip()
        if not cleaned or "<think>" in cleaned.lower():
            return None
        return cleaned

    def _parse_json_text(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            text = match.group(0)
        try:
            parsed = json.loads(text)
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            return parsed
        except json.JSONDecodeError:
            repaired = self._repair_json_like_text(text)
            if repaired is not None:
                return repaired
            return {
                "conclusion": text,
                "evidence_summary": "模型未按 JSON 返回，已按纯文本兜底处理。",
                "cautions": "",
                "related_entities": [],
                "follow_up_questions": [],
            }

    def _compose_structured_system_prompt(
        self,
        *,
        system_prompt: str,
        output_schema: dict[str, Any] | None,
        required_keys: list[str],
        agent_key: str | None,
    ) -> str:
        module_name = agent_key or "current_agent"
        schema_text = json.dumps(output_schema, ensure_ascii=False, indent=2) if output_schema else ""
        key_lines = "\n".join(f"- {key}" for key in required_keys) if required_keys else "- 请按约定 schema 返回"
        hard_rules = (
            "你正在药食同源研发协同工作流中执行单个模块。\n"
            f"当前模块：{module_name}。\n"
            "以下规则优先级高于任何可编辑提示词内容，必须严格遵守：\n"
            "1. 只能基于 user 消息中的 payload 作答，不得编造不存在的图谱证据或外部结论。\n"
            "2. 只能输出一个 JSON 对象，禁止输出 Markdown、代码块、解释性前后缀、<think> 标签。\n"
            "3. 顶层字段名必须完全匹配系统要求；字段暂无内容时也必须返回空字符串、空数组或空对象。\n"
            "4. 不要省略必需字段，不要改名，不要输出未约定的顶层字段。\n"
            "5. 如果提示词提到尚未实现的模块，例如工艺适配、市场预测，请忽略它们，只围绕当前 payload 和当前模块返回结果。\n"
            "6. 回答必须简洁、专业、可落地，避免夸大功效。\n"
            f"必须返回的顶层字段：\n{key_lines}\n"
        )
        if schema_text:
            hard_rules += f"系统参考 schema：\n{schema_text}\n"
        if not system_prompt.strip():
            return hard_rules
        return f"{hard_rules}\n以下是当前模块的业务提示词，请在不违反上述硬性要求的前提下执行：\n{system_prompt.strip()}"

    def _resolve_required_keys(
        self,
        output_schema: dict[str, Any] | None,
        fallback: dict[str, Any],
        required_keys: list[str] | None,
    ) -> list[str]:
        keys: list[str] = []
        for key in required_keys or []:
            if key and key not in keys:
                keys.append(key)
        properties = output_schema.get("properties", {}) if isinstance(output_schema, dict) else {}
        if isinstance(properties, dict):
            for key in properties.keys():
                if key and key not in keys:
                    keys.append(key)
        for key in fallback.keys():
            if key and key not in keys:
                keys.append(key)
        return keys

    def _matches_expected_shape(self, parsed: dict[str, Any], expected_keys: list[str]) -> bool:
        if not expected_keys:
            return True
        overlap = sum(1 for key in expected_keys if key in parsed)
        return overlap >= max(1, min(2, len(expected_keys)))

    def _normalize_structured_output(
        self,
        parsed: dict[str, Any],
        fallback: dict[str, Any],
        expected_keys: list[str],
    ) -> dict[str, Any]:
        if not expected_keys:
            return parsed
        normalized: dict[str, Any] = {}
        for key in expected_keys:
            value = parsed.get(key)
            if value is None:
                value = fallback.get(key)
            normalized[key] = value
        return normalized

    def _fallback_answer(self, context: dict[str, Any], error_message: str | None = None) -> dict[str, Any]:
        names = [item.get("name") for item in context.get("selected_entities", [])][:5]
        configured = bool(settings.minimax_api_key)
        if configured and error_message:
            direct = "MiniMax 已配置，但本次调用失败，系统已自动切换为基于知识图谱检索结果的本地降级回答。"
            cautions = error_message
        else:
            direct = "当前未配置 MiniMax API Key，系统返回基于知识图谱检索结果的本地兜底说明。"
            cautions = "请在后端环境变量中配置 MINIMAX_API_KEY，以启用完整问答生成。"
        conclusion = (
            f"【核心结论】\n{direct}\n\n"
            f"【图谱依据】\n命中的相关实体包括：{', '.join(names) if names else '暂无明确实体'}。\n\n"
            f"【注意事项】\n{cautions}\n\n"
            "【总结建议】\n当前答案仅能作为图谱检索结果摘要。请完善 MiniMax 配置后重新提问，或点击证据子图核验命中的实体关系。"
        )
        return {
            "conclusion": conclusion,
            "evidence_summary": f"命中的相关实体包括：{', '.join(names) if names else '暂无明确实体'}。",
            "cautions": cautions,
            "related_entities": names,
            "follow_up_questions": ["请介绍这些实体之间的关系", "这个结果的证据链是什么？"],
            "_reasoning_details": None,
            "_fallback": True,
        }

    def _fallback_analysis(self, question: str) -> dict[str, Any]:
        asked_aspects: list[str] = []
        if any(token in question for token in ["功效", "作用", "主治", "适应"]):
            asked_aspects.append("efficacy")
        if any(token in question for token in ["成分", "成份"]):
            asked_aspects.append("ingredient")
        if "靶点" in question:
            asked_aspects.append("target")
        if any(token in question for token in ["方剂", "方子", "方"]):
            asked_aspects.append("formula")
        if any(token in question for token in ["症状", "疾病", "病"]):
            asked_aspects.append("disease")
        if any(token in question for token in ["禁忌", "慎用", "注意"]):
            asked_aspects.append("caution")
        if not asked_aspects:
            asked_aspects.append("usage")

        question_type = "entity_explanation"
        if any(token in question for token in ["替换", "替代", "代替", "取代", "换成", "换掉"]):
            question_type = "formula_replacement"
        elif any(token in question for token in ["体质", "气虚质", "阳虚质", "阴虚质", "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质"]):
            question_type = "constitution_recommendation"
        elif any(token in question for token in ["成药", "产品", "商品", "消费者", "消费", "口感", "好评", "复购", "送礼", "老人", "宝妈", "价格", "剂型"]):
            question_type = "product_recommendation"
        if "靶点" in question or "成分" in question or "功效" in question:
            question_type = "herb_efficacy"
        if question_type == "entity_explanation" and any(token in question for token in ["症状", "疾病", "病"]) and any(token in question for token in ["方剂", "方子", "方"]):
            question_type = "disease_relation"
        elif question_type == "entity_explanation" and any(token in question for token in ["方剂", "方子", "方"]):
            question_type = "formula_relation"

        search_terms = self._fallback_search_terms(question)
        return {
            "question_type": question_type,
            "needs_multi_entity": any(token in question for token in ["、", "以及", "和", "并且"]),
            "asked_aspects": asked_aspects,
            "summary": "使用本地规则完成问题解析。",
            "search_terms": search_terms,
        }

    def _fallback_search_terms(self, question: str) -> list[str]:
        search_terms: list[str] = []
        normalized = question
        for token in ["药食同源", "药材", "食材", "相关的", "相关", "有哪些", "什么", "请问", "？？？", "？？", "？", "?", "。", "，", ",", "、"]:
            normalized = normalized.replace(token, " ")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if normalized:
            search_terms.extend([part for part in normalized.split(" ") if part])

        synonym_map = {
            "高血压": ["高血压", "Hypertension"],
            "糖尿病": ["糖尿病", "Diabetes"],
            "失眠": ["失眠", "Insomnia"],
            "头痛": ["头痛", "Headache"],
            "咳嗽": ["咳嗽", "Cough"],
        }
        for chinese, terms in synonym_map.items():
            if chinese in question:
                for term in terms:
                    if term not in search_terms:
                        search_terms.append(term)
        return search_terms[:8]

    def _repair_json_like_text(self, text: str) -> dict[str, Any] | None:
        def extract_string(field: str) -> str | None:
            pattern = rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*)"'
            match = re.search(pattern, text, re.S)
            if not match:
                return None
            raw_value = match.group(1)
            try:
                return json.loads(f'"{raw_value}"')
            except json.JSONDecodeError:
                return raw_value.replace('\\"', '"').replace("\\n", "\n")

        def extract_array(field: str) -> list[Any]:
            pattern = rf'"{field}"\s*:\s*(\[[\s\S]*?\])(?=\s*,\s*"[A-Za-z_]+"|\s*\}})'
            match = re.search(pattern, text, re.S)
            if not match:
                return []
            raw = match.group(1)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return []

        conclusion = extract_string("conclusion")
        evidence_summary = extract_string("evidence_summary")
        cautions = extract_string("cautions")
        related_entities = extract_array("related_entities")
        follow_up_questions = extract_array("follow_up_questions")
        if conclusion is None and evidence_summary is None:
            return None
        return {
            "conclusion": conclusion or "",
            "evidence_summary": evidence_summary or "",
            "cautions": cautions or "",
            "related_entities": related_entities,
            "follow_up_questions": follow_up_questions,
        }
