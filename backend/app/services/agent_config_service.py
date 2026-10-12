# -*- coding: utf-8 -*-
"""工作流 Agent 配置服务（2026-10-12 新增）。

职责：
- 只读总览：把「静态定义（AGENT_STEP_DEFS）+ 当前 DB 配置 + 输出契约 + 最近运行回放」拼成一份，
  供管理端「工作流逻辑」页展示。
- 编辑：白名单字段校验 + 参数钳制 + 版本自增 + 落版本快照（含修改人）。
- 回滚：把历史快照写回配置，并再生成一条新版本（历史只增不改）。
- 试运行：用当前配置对单步跑一次真实调用，不写 run/step 记录、不影响运行统计。

安全边界：`key`/`scenario`/`agent_key`/`output_schema` 一律不可改（首期），改动请求直接拒绝。
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services.rnd_workflow_orchestrator import AGENT_STEP_DEFS, RnDWorkflowOrchestrator

WORKFLOW_SCENARIO = "rnd_workflow"
EDITABLE_FIELDS = ("name", "description", "system_prompt", "is_active", "temperature", "max_tokens")
LOCKED_FIELDS = ("key", "scenario", "agent_key", "output_schema", "answer_schema", "version", "is_customized")

_DRY_RUN_QUESTION = "试运行：请围绕「药食同源代餐粉」给出研发方案要点"


class AgentConfigError(ValueError):
    """配置校验失败（调用方应转成 400）。"""


def step_defs() -> tuple:
    return AGENT_STEP_DEFS


def get_step_def(agent_key: str):
    for item in AGENT_STEP_DEFS:
        if item.agent_key == agent_key:
            return item
    raise AgentConfigError(f"未知的 Agent：{agent_key}")


def _fallback_for(orchestrator: RnDWorkflowOrchestrator, agent_key: str, brief: dict[str, Any],
                  question: str) -> dict[str, Any]:
    """取该步的本地兜底结果：它既是试运行的 fallback，也是该步「输出契约」的来源。"""
    if agent_key == "master_control":
        return orchestrator._master_fallback(brief, question, final_mode=False)
    if agent_key == "master_control_final":
        return orchestrator._master_fallback(brief, question, final_mode=True)
    if agent_key == "formula_generation":
        return orchestrator._formula_fallback(brief, [], [])
    if agent_key == "efficacy_prediction":
        return orchestrator._efficacy_fallback(brief, [])
    if agent_key == "flavor_prediction":
        return orchestrator._flavor_fallback([])
    if agent_key == "replacement_mapping":
        return orchestrator._replacement_fallback([], [], brief=brief, efficacy_payload={}, flavor_payload={})
    raise AgentConfigError(f"未知的 Agent：{agent_key}")


def _serialize_step_run(row) -> dict[str, Any]:
    step, question, run_status = row
    return {
        "step_id": step.id,
        "run_id": step.run_id,
        "question": (question or "")[:80],
        "run_status": run_status,
        "status": step.status,
        "latency_ms": step.latency_ms,
        "used_fallback": bool(step.used_fallback),
        "skipped": bool(step.skipped),
        "prompt_version": step.prompt_version,
        "has_graph_snapshot": bool(step.graph_snapshot_id),
        "created_at": step.created_at.isoformat() if step.created_at else None,
    }


def build_overview(repository, orchestrator: RnDWorkflowOrchestrator) -> list[dict[str, Any]]:
    """六步总览：静态定义 + 当前配置 + 输出契约 + 最近运行回放。"""
    brief = orchestrator._build_brief(_DRY_RUN_QUESTION, None)
    overview: list[dict[str, Any]] = []
    for item in AGENT_STEP_DEFS:
        prompt = repository.get_prompt_template_by_scenario_agent(
            WORKFLOW_SCENARIO, item.agent_key, include_inactive=True
        )
        if prompt is None and item.agent_key == "master_control_final":
            prompt = repository.get_prompt_template_by_scenario_agent(
                WORKFLOW_SCENARIO, "master_control", include_inactive=True
            )
        try:
            contract_keys = list(_fallback_for(orchestrator, item.agent_key, brief, _DRY_RUN_QUESTION).keys())
        except Exception:  # noqa: BLE001 - 契约推导失败不应影响总览
            contract_keys = []
        runs = [_serialize_step_run(row) for row in repository.list_recent_step_runs(item.agent_key, limit=8)]
        overview.append({
            "agent_key": item.agent_key,
            "sequence": item.sequence,
            "name": item.name,
            "duty": item.duty,
            "upstream": list(item.upstream),
            "downstream": list(item.downstream),
            "produces_graph_snapshot": item.produces_graph_snapshot,
            "contract_keys": contract_keys,
            "config": None if prompt is None else {
                "prompt_id": prompt.id,
                "key": prompt.key,
                "scenario": prompt.scenario,
                "agent_key": prompt.agent_key,
                "name": prompt.name,
                "description": prompt.description,
                "system_prompt": prompt.system_prompt,
                "system_prompt_chars": len(prompt.system_prompt or ""),
                "is_active": prompt.is_active,
                "is_customized": prompt.is_customized,
                "version": prompt.version,
                "updated_at": prompt.updated_at.isoformat() if prompt.updated_at else None,
                "temperature": prompt.temperature,
                "max_tokens": prompt.max_tokens,
            },
            "recent_runs": runs,
            "last_run": runs[0] if runs else None,
        })
    return overview


def _clamp(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    if "system_prompt" in payload:
        text = (payload.get("system_prompt") or "").strip()
        if not text:
            raise AgentConfigError("提示词不能为空")
        if len(text) > settings.agent_prompt_max_chars:
            raise AgentConfigError(f"提示词过长（{len(text)} 字），上限 {settings.agent_prompt_max_chars} 字")
        cleaned["system_prompt"] = text
    if "name" in payload:
        name = (payload.get("name") or "").strip()
        if not name:
            raise AgentConfigError("名称不能为空")
        cleaned["name"] = name[:128]
    if "description" in payload:
        cleaned["description"] = (payload.get("description") or "").strip() or None
    if "is_active" in payload:
        cleaned["is_active"] = bool(payload.get("is_active"))
    if "temperature" in payload:
        value = payload.get("temperature")
        if value is None or value == "":
            cleaned["temperature"] = None
        else:
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise AgentConfigError("temperature 必须是数字") from exc
            if not (settings.agent_temperature_min <= number <= settings.agent_temperature_max):
                raise AgentConfigError(
                    f"temperature 需在 {settings.agent_temperature_min}–{settings.agent_temperature_max} 之间"
                )
            cleaned["temperature"] = number
    if "max_tokens" in payload:
        value = payload.get("max_tokens")
        if value is None or value == "":
            cleaned["max_tokens"] = None
        else:
            try:
                number = int(value)
            except (TypeError, ValueError) as exc:
                raise AgentConfigError("max_tokens 必须是整数") from exc
            if not (settings.agent_max_tokens_min <= number <= settings.agent_max_tokens_max):
                raise AgentConfigError(
                    f"max_tokens 需在 {settings.agent_max_tokens_min}–{settings.agent_max_tokens_max} 之间"
                )
            cleaned["max_tokens"] = number
    return cleaned


def update_agent_config(repository, agent_key: str, payload: dict[str, Any], admin) -> dict[str, Any]:
    """保存 Agent 配置：白名单校验 → 写回 → 版本 +1 → 落版本快照。"""
    item = get_step_def(agent_key)
    locked = [field for field in LOCKED_FIELDS if field in payload]
    if locked:
        raise AgentConfigError(f"以下字段本期不可编辑：{'、'.join(locked)}")
    unknown = [field for field in payload if field not in EDITABLE_FIELDS]
    if unknown:
        raise AgentConfigError(f"不支持的字段：{'、'.join(unknown)}")

    prompt = repository.get_prompt_template_by_scenario_agent(WORKFLOW_SCENARIO, agent_key, include_inactive=True)
    if prompt is None:
        raise AgentConfigError(f"未找到 {item.name}（{agent_key}）的提示词模板")

    cleaned = _clamp(payload)
    changed: list[str] = []
    for field, value in cleaned.items():
        if getattr(prompt, field, None) != value:
            changed.append(field)
            setattr(prompt, field, value)
    if not changed:
        return {"changed": [], "version": prompt.version, "message": "没有变化，未生成新版本"}

    prompt.is_customized = True
    prompt.version = int(prompt.version or 0) + 1
    revision = repository.create_agent_revision(
        prompt_template_id=prompt.id,
        agent_key=prompt.agent_key,
        scenario=prompt.scenario,
        version=prompt.version,
        name=prompt.name,
        description=prompt.description,
        system_prompt=prompt.system_prompt,
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
        is_active=prompt.is_active,
        output_schema=prompt.output_schema,
        changed_fields=changed,
        change_note=(payload.get("change_note") or "")[:255] or None,
        changed_by=getattr(admin, "id", None),
        changed_by_name=getattr(admin, "display_name", None) or getattr(admin, "username", None),
    )
    repository.session.commit()
    return {
        "changed": changed,
        "version": prompt.version,
        "revision_id": revision.id,
        "changed_by_name": revision.changed_by_name,
        "message": "已保存并生成新版本（下一次运行即生效）",
    }


def list_revisions(repository, agent_key: str, *, limit: int = 50) -> list[dict[str, Any]]:
    prompt = repository.get_prompt_template_by_scenario_agent(WORKFLOW_SCENARIO, agent_key, include_inactive=True)
    if prompt is None:
        raise AgentConfigError(f"未找到 {agent_key} 的提示词模板")
    rows = repository.list_agent_revisions(prompt.id, limit=limit)
    return [
        {
            "id": row.id,
            "version": row.version,
            "changed_fields": row.changed_fields or [],
            "change_note": row.change_note,
            "changed_by_name": row.changed_by_name,
            "is_active": row.is_active,
            "temperature": row.temperature,
            "max_tokens": row.max_tokens,
            "system_prompt_chars": len(row.system_prompt or ""),
            "system_prompt": row.system_prompt,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def rollback_to_revision(repository, agent_key: str, revision_id: str, admin) -> dict[str, Any]:
    """回滚到历史版本：写回快照内容，并再生成一条新版本（历史只增不改）。"""
    prompt = repository.get_prompt_template_by_scenario_agent(WORKFLOW_SCENARIO, agent_key, include_inactive=True)
    if prompt is None:
        raise AgentConfigError(f"未找到 {agent_key} 的提示词模板")
    revision = repository.get_agent_revision(revision_id)
    if revision is None or revision.prompt_template_id != prompt.id:
        raise AgentConfigError("该版本不存在或不属于此 Agent")

    changed = []
    for field in ("name", "description", "system_prompt", "temperature", "max_tokens", "is_active"):
        value = getattr(revision, field)
        if getattr(prompt, field, None) != value:
            changed.append(field)
            setattr(prompt, field, value)
    prompt.is_customized = True
    prompt.version = int(prompt.version or 0) + 1
    new_revision = repository.create_agent_revision(
        prompt_template_id=prompt.id,
        agent_key=prompt.agent_key,
        scenario=prompt.scenario,
        version=prompt.version,
        name=prompt.name,
        description=prompt.description,
        system_prompt=prompt.system_prompt,
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
        is_active=prompt.is_active,
        output_schema=prompt.output_schema,
        changed_fields=changed,
        change_note=f"回滚到 v{revision.version}",
        changed_by=getattr(admin, "id", None),
        changed_by_name=getattr(admin, "display_name", None) or getattr(admin, "username", None),
    )
    repository.session.commit()
    return {
        "rolled_back_from": revision.version,
        "version": prompt.version,
        "changed": changed,
        "revision_id": new_revision.id,
        "message": f"已回滚到 v{revision.version}，并记为 v{prompt.version}",
    }


def dry_run(orchestrator: RnDWorkflowOrchestrator, repository, agent_key: str,
            question: str | None = None) -> dict[str, Any]:
    """单步试运行：用当前配置跑一次真实调用，**不写 run/step 记录**。

    上游数据用该步的本地兜底样本替代（界面已注明），因此这是"提示词与参数是否还能产出
    合法结构化输出"的检查，不模拟真实上游。
    """
    item = get_step_def(agent_key)
    brief = orchestrator._build_brief((question or "").strip() or _DRY_RUN_QUESTION, None)
    fallback = _fallback_for(orchestrator, agent_key, brief, question or _DRY_RUN_QUESTION)
    prompt = repository.get_prompt_template_by_scenario_agent(WORKFLOW_SCENARIO, agent_key, include_inactive=True)
    if prompt is None and agent_key == "master_control_final":
        prompt = repository.get_prompt_template_by_scenario_agent(
            WORKFLOW_SCENARIO, "master_control", include_inactive=True
        )
    payload = {
        "brief": brief,
        "question": (question or "").strip() or _DRY_RUN_QUESTION,
        "note": "试运行：上游数据以本地兜底样本替代，payload 为简化形态",
        "upstream_sample": {name: {} for name in item.upstream},
    }
    if prompt is not None and not prompt.is_active:
        return {
            "agent_key": agent_key,
            "name": item.name,
            "skipped": True,
            "used_fallback": True,
            "elapsed_ms": 0,
            "note": "该 Agent 已停用：正式运行时会跳过模型调用并直接使用兜底结果，试运行不做模型调用",
            "required_keys": list(fallback.keys()),
            "output": fallback,
        }
    output, elapsed_ms, used_fallback = orchestrator.llm_client.generate_structured_output(
        system_prompt=prompt.system_prompt if prompt else "",
        payload=payload,
        fallback=fallback,
        output_schema=prompt.output_schema if prompt else None,
        required_keys=list(fallback.keys()),
        agent_key=agent_key,
        temperature=prompt.temperature if prompt else None,
        max_completion_tokens=(prompt.max_tokens if prompt and prompt.max_tokens else 1000),
    )
    return {
        "agent_key": agent_key,
        "name": item.name,
        "skipped": False,
        "used_fallback": used_fallback,
        "elapsed_ms": elapsed_ms,
        "prompt_version": f"v{prompt.version}" if prompt else "seed",
        "temperature": prompt.temperature if prompt else None,
        "max_tokens": (prompt.max_tokens if prompt else None),
        "required_keys": list(fallback.keys()),
        "output": output,
        "note": "上游用兜底样本；本次试运行不写运行记录、不计入统计，但会消耗少量模型额度",
    }
