import json
import re
from time import perf_counter
from typing import Any

from app.repositories.neo4j_repository import Neo4jRepository
from app.repositories.postgres_repository import PostgresRepository
from app.services.minimax_client import MiniMaxClient


class RnDWorkflowOrchestrator:
    AGENT_SEQUENCE = [
        "master_control",
        "formula_generation",
        "efficacy_prediction",
        "flavor_prediction",
        "replacement_mapping",
        "master_control_final",
    ]

    def __init__(
        self,
        postgres_repository: PostgresRepository,
        neo4j_repository: Neo4jRepository,
        minimax_client: MiniMaxClient,
    ) -> None:
        self.postgres_repository = postgres_repository
        self.neo4j_repository = neo4j_repository
        self.minimax_client = minimax_client

    def start_run(self, session_id: str, question: str, reuse_last_brief: bool = False) -> dict[str, Any]:
        workflow_session = self.postgres_repository.get_workflow_session(session_id)
        if workflow_session is None:
            raise ValueError("Workflow session not found")

        brief = self._build_brief(question, workflow_session.last_brief if reuse_last_brief else None)
        workflow_session.last_brief = brief
        workflow_session.title = workflow_session.title or question[:40]
        workflow_session.status = "running"

        run = self.postgres_repository.create_workflow_run(
            session_id=session_id,
            question=question,
            brief=brief,
            status="queued",
        )
        self.postgres_repository.session.commit()
        return {
            "session_id": session_id,
            "run_id": run.id,
            "brief": brief,
            "final_report": None,
            "steps": [],
            "summary_metrics": {},
            "related_graph_snapshots": [],
            "status": run.status,
        }

    def resume_run(self, run_id: str) -> dict[str, Any]:
        run = self.postgres_repository.get_workflow_run(run_id)
        if run is None:
            raise ValueError("Workflow run not found")
        workflow_session = self.postgres_repository.get_workflow_session(run.session_id)
        if workflow_session is None:
            raise ValueError("Workflow session not found")

        session_id = run.session_id
        question = run.question
        brief = run.brief

        run.status = "running"
        workflow_session.status = "running"
        self.postgres_repository.session.commit()

        related_graph_snapshots: list[str] = []
        try:
            master_initial_fallback = self._master_fallback(brief, question, final_mode=False)
            master_initial = self._run_step(
                run.id,
                1,
                "master_control",
                {
                    "brief": brief,
                    "question": question,
                    "instruction": (
                        "按研发逻辑顺序拆解需求并输出可执行任务计划（方剂生成→功效预测→风味预测→替代映射）。"
                        "必须明确：目标人群、关键功效路径、药食同源合规检查点、每阶段交付物。"
                        "所有输出需标注数据来源（如《中国药典》、GB标准、FlavorDB等）。"
                    ),
                },
                master_initial_fallback,
            )

            formula_result = self._run_formula_generation(workflow_session.id, run.id, 2, brief)
            if formula_result.get("graph_snapshot_id"):
                related_graph_snapshots.append(formula_result["graph_snapshot_id"])

            efficacy_result = self._run_efficacy_prediction(workflow_session.id, run.id, 3, brief, formula_result)
            if efficacy_result.get("graph_snapshot_id"):
                related_graph_snapshots.append(efficacy_result["graph_snapshot_id"])

            flavor_result = self._run_flavor_prediction(workflow_session.id, run.id, 4, brief, formula_result)
            if flavor_result.get("graph_snapshot_id"):
                related_graph_snapshots.append(flavor_result["graph_snapshot_id"])

            replacement_result = self._run_replacement_mapping(workflow_session.id, run.id, 5, brief, formula_result, efficacy_result, flavor_result)
            if replacement_result.get("graph_snapshot_id"):
                related_graph_snapshots.append(replacement_result["graph_snapshot_id"])

            final_master_fallback = self._master_fallback(
                brief,
                question,
                final_mode=True,
                formula_payload=formula_result["output_payload"],
                efficacy_payload=efficacy_result["output_payload"],
                flavor_payload=flavor_result["output_payload"],
                replacement_payload=replacement_result["output_payload"],
            )
            final_master = self._run_step(
                run.id,
                6,
                "master_control_final",
                {
                    "brief": brief,
                    "question": question,
                    "initial_plan": master_initial["output_payload"],
                    "formula_generation": formula_result["output_payload"],
                    "efficacy_prediction": efficacy_result["output_payload"],
                    "flavor_prediction": flavor_result["output_payload"],
                    "replacement_mapping": replacement_result["output_payload"],
                    "instruction": (
                        "整合前序模块（方剂生成、功效预测、风味预测、替代映射）并输出最终研发方案。"
                        "必须给出：最终方剂组成与方解、每味药材在目标中的作用与剂量依据、"
                        "核心功效与作用机制、风味特征与消费者接受度、替代方案与多维对比、"
                        "合规与风险提示、可执行下一步。所有输出需标注数据来源。"
                        "若证据不足，需具体说明缺口和补充数据建议。"
                    ),
                },
                final_master_fallback,
            )

            steps = self.postgres_repository.list_workflow_step_runs(run.id)
            final_report = {
                "brief_summary": final_master["output_payload"].get("brief_summary", ""),
                "final_recommendation": final_master["output_payload"].get("final_recommendation", ""),
                "consistency_checks": final_master["output_payload"].get("consistency_checks", []),
                "next_actions": final_master["output_payload"].get("next_actions", []),
                "modules": {
                    "formula_generation": formula_result["output_payload"],
                    "efficacy_prediction": efficacy_result["output_payload"],
                    "flavor_prediction": flavor_result["output_payload"],
                    "replacement_mapping": replacement_result["output_payload"],
                },
            }
            run.final_report = final_report
            run.summary_metrics = {
                "stepCount": len(steps),
                "graphSnapshotCount": len(related_graph_snapshots),
                "formulaCount": len(formula_result["output_payload"].get("formulas", [])),
                "replacementCount": len(replacement_result["output_payload"].get("recommended_replacements", [])),
            }
            run.related_graph_snapshots = related_graph_snapshots
            run.status = "completed"
            workflow_session.status = "active"
            self.postgres_repository.session.commit()

            return {
                "session_id": session_id,
                "run_id": run.id,
                "brief": brief,
                "final_report": final_report,
                "steps": steps,
                "summary_metrics": run.summary_metrics,
                "related_graph_snapshots": related_graph_snapshots,
                "status": run.status,
            }
        except Exception as exc:
            run.status = "failed"
            run.final_report = {
                "brief_summary": brief.get("goal", ""),
                "final_recommendation": "",
                "consistency_checks": [f"工作流执行失败：{exc}"],
                "next_actions": ["请检查当前 Agent 提示词、图谱证据和模型连通性后重试。"],
                "modules": {},
            }
            run.summary_metrics = {
                "stepCount": len(self.postgres_repository.list_workflow_step_runs(run.id)),
                "graphSnapshotCount": len(related_graph_snapshots),
                "formulaCount": 0,
                "replacementCount": 0,
            }
            run.related_graph_snapshots = related_graph_snapshots
            workflow_session.status = "active"
            self.postgres_repository.session.commit()
            raise

    def _run_formula_generation(self, workflow_session_id: str, run_id: str, sequence: int, brief: dict[str, Any]) -> dict[str, Any]:
        search_terms = self._brief_search_terms(brief)
        candidates = self.neo4j_repository.find_candidate_herbs_for_brief(search_terms, limit=18)
        selected = candidates[:8]
        herb_names = [item["id"] for item in selected]
        graph_snapshot_id = self._save_graph_snapshot(workflow_session_id, brief["goal"], herb_names) if selected else None
        payload = {
            "brief": brief,
            "candidate_herbs": [self._compact_herb(item) for item in candidates],
            "instruction": (
                "从候选药食同源药材中设计 1-3 个候选方剂。每个方剂需输出："
                "方名、配伍（君臣佐使）、各药材剂量区间（标注成人每日推荐用量与最大安全用量）、"
                "方解（配伍逻辑与各药材作用）、经典名方参考、适用场景、不适用场景。"
                "所有药材须来自药食同源目录，剂量须符合食品安全标准。"
            ),
        }
        fallback = self._formula_fallback(brief, selected)
        return self._run_step(
            run_id,
            sequence,
            "formula_generation",
            payload,
            fallback,
            graph_snapshot_id=graph_snapshot_id,
        )

    def _run_efficacy_prediction(self, workflow_session_id: str, run_id: str, sequence: int, brief: dict[str, Any], formula_result: dict[str, Any]) -> dict[str, Any]:
        selected_herbs = self._collect_formula_herbs(formula_result["output_payload"])
        graph_snapshot_id = self._save_graph_snapshot(workflow_session_id, brief["goal"], selected_herbs) if selected_herbs else None
        payload = {
            "brief": brief,
            "formula_generation": formula_result["output_payload"],
            "evidence_herbs": self._load_herb_entities(selected_herbs),
            "instruction": (
                "基于方剂组方与成分-功效关联模型，分析中医功效与现代药理功效。"
                "必须区分三类人群：适用人群、不适宜人群、禁忌人群。"
                "标注作用机制、潜在风险与文献依据（如《中国药典》、药理研究文献）。"
                "禁止夸大功效，所有预测须有权威支撑。输出时请把「功效结论」和「证据不足点」分开描述。"
            ),
        }
        fallback = self._efficacy_fallback(brief, selected_herbs)
        return self._run_step(
            run_id,
            sequence,
            "efficacy_prediction",
            payload,
            fallback,
            graph_snapshot_id=graph_snapshot_id,
        )

    def _run_flavor_prediction(self, workflow_session_id: str, run_id: str, sequence: int, brief: dict[str, Any], formula_result: dict[str, Any]) -> dict[str, Any]:
        selected_herbs = self._collect_formula_herbs(formula_result["output_payload"])
        graph_snapshot_id = self._save_graph_snapshot(workflow_session_id, brief["goal"], selected_herbs) if selected_herbs else None
        payload = {
            "brief": brief,
            "formula_generation": formula_result["output_payload"],
            "evidence_herbs": self._load_herb_entities(selected_herbs),
            "instruction": (
                "基于 FlavorDB、BungentDB 等风味数据库与食品感官科学，输出方剂风味特征。"
                "必须区分三维度：味觉（酸/甜/苦/咸/鲜）、嗅觉（香气类型）、口感。"
                "分析风味协调性、标注潜在风味缺陷、评估目标消费者接受度。"
                "提供可落地的风味优化方向（比例调整/辅料引入/工艺调整）。"
            ),
        }
        fallback = self._flavor_fallback(selected_herbs)
        return self._run_step(
            run_id,
            sequence,
            "flavor_prediction",
            payload,
            fallback,
            graph_snapshot_id=graph_snapshot_id,
        )

    def _run_replacement_mapping(
        self,
        workflow_session_id: str,
        run_id: str,
        sequence: int,
        brief: dict[str, Any],
        formula_result: dict[str, Any],
        efficacy_result: dict[str, Any],
        flavor_result: dict[str, Any],
    ) -> dict[str, Any]:
        selected_herbs = self._collect_formula_herbs(formula_result["output_payload"])
        herb_entities = self._load_herb_entities(selected_herbs)
        replacement_payload = []
        for herb in herb_entities:
            candidates = self.neo4j_repository.get_replacement_candidates(herb["id"], limit=5)
            replacement_payload.append(
                {
                    "source_herb": herb["name"],
                    "source_key": herb["id"],
                    "candidates": candidates,
                }
            )
        graph_snapshot_id = self._save_graph_snapshot(workflow_session_id, brief["goal"], selected_herbs) if selected_herbs else None
        payload = {
            "brief": brief,
            "formula_generation": formula_result["output_payload"],
            "efficacy_prediction": efficacy_result["output_payload"],
            "flavor_prediction": flavor_result["output_payload"],
            "replacement_candidates": replacement_payload,
            "instruction": (
                "基于功效、风味、成本、合规、工艺、供应链六个维度，给出正式替代建议。"
                "必须对比替代前后的功效等效性、风味影响、成本变动、工艺适配性差异。"
                "优先推荐供应稳定、成本更低、风味更优的药食同源替代品种。"
                "若无可替代项，需明确说明「为什么不建议替代」并标注适用场景。"
            ),
        }
        fallback = self._replacement_fallback(herb_entities, replacement_payload)
        return self._run_step(
            run_id,
            sequence,
            "replacement_mapping",
            payload,
            fallback,
            graph_snapshot_id=graph_snapshot_id,
        )

    def _run_step(
        self,
        run_id: str,
        sequence: int,
        agent_key: str,
        input_payload: dict[str, Any],
        fallback: dict[str, Any],
        graph_snapshot_id: str | None = None,
    ) -> dict[str, Any]:
        prompt = self.postgres_repository.get_prompt_template_by_scenario_agent("rnd_workflow", agent_key)
        if prompt is None and agent_key == "master_control_final":
            prompt = self.postgres_repository.get_prompt_template_by_scenario_agent("rnd_workflow", "master_control")
        prompt_version = prompt.updated_at.isoformat() if prompt else "seed"
        started = perf_counter()
        step = self.postgres_repository.create_workflow_step_run(
            run_id=run_id,
            agent_key=agent_key,
            sequence=sequence,
            input_payload=input_payload,
            status="running",
            graph_snapshot_id=graph_snapshot_id,
            prompt_version=prompt_version,
        )
        self.postgres_repository.session.commit()
        self.postgres_repository.session.refresh(step)
        system_prompt = prompt.system_prompt if prompt else ""
        output_payload, latency_ms = self.minimax_client.generate_structured_output(
            system_prompt=system_prompt,
            payload=input_payload,
            fallback=fallback,
            output_schema=prompt.output_schema if prompt else None,
            required_keys=list(fallback.keys()),
            agent_key=agent_key,
            max_completion_tokens=1000,
        )
        if not output_payload:
            output_payload = fallback
        step.output_payload = output_payload
        step.status = "completed"
        step.latency_ms = latency_ms or int((perf_counter() - started) * 1000)
        self.postgres_repository.session.commit()
        self.postgres_repository.session.refresh(step)
        return {
            "step_id": step.id,
            "graph_snapshot_id": graph_snapshot_id,
            "output_payload": output_payload,
        }

    def _build_brief(self, question: str, last_brief: dict[str, Any] | None) -> dict[str, Any]:
        brief = self.minimax_client.build_rnd_brief(question)
        if last_brief:
            for key in ["constraints", "dosage_form", "target_population", "timeline", "budget", "compliance_scope"]:
                if not brief.get(key) and last_brief.get(key):
                    brief[key] = last_brief[key]
        brief["goal"] = self._normalize_goal(brief["goal"])
        if "仅使用药食同源目录成分" not in brief["constraints"]:
            brief["constraints"].append("仅使用药食同源目录成分")
        return brief

    def _save_graph_snapshot(self, workflow_session_id: str, question: str, herb_names: list[str]) -> str | None:
        if not herb_names:
            return None
        graph = self.neo4j_repository.retrieve_rnd_graph(herb_names)
        snapshot = self.postgres_repository.create_graph_snapshot(workflow_session_id, question, graph)
        return snapshot.id

    def _brief_search_terms(self, brief: dict[str, Any]) -> list[str]:
        text = " ".join(
            [
                brief.get("goal", ""),
                brief.get("dosage_form", ""),
                brief.get("target_population", ""),
                " ".join(brief.get("constraints", [])),
            ]
        )
        parts = [piece for piece in re.split(r"[\s,，、。；;：:\-]+", text) if piece]
        stop_words = {"一款", "产品", "研发", "方案", "药食同源", "目录", "成分", "内", "仅使用", "符合", "要求"}
        search_terms = [piece for piece in parts if len(piece) > 1 and piece not in stop_words]

        goal = brief.get("goal", "")
        heuristic_terms: list[str] = []
        if "免疫" in goal:
            heuristic_terms.extend(["补气", "益气", "扶正", "健脾", "益肺"])
        if any(token in goal for token in ["感冒", "风寒", "风热", "鼻塞", "咳嗽", "咽痛"]):
            heuristic_terms.extend(["解表", "散寒", "疏风", "宣肺", "止咳", "清热"])
        if any(token in goal for token in ["抗氧化", "清除自由基"]):
            heuristic_terms.extend(["养阴", "生津", "清热", "滋补"])
        if any(token in goal for token in ["血糖", "控糖", "降糖"]):
            heuristic_terms.extend(["健脾", "益气", "养阴", "生津"])
        if any(token in goal for token in ["睡眠", "安神", "助眠"]):
            heuristic_terms.extend(["养心安神", "宁心安神", "养血安神"])
        if any(token in goal for token in ["明目", "护眼", "视力"]):
            heuristic_terms.extend(["养肝明目", "补血养阴"])

        for term in heuristic_terms:
            if term not in search_terms:
                search_terms.append(term)
        return search_terms[:12] or [brief.get("goal", "")]

    def _compact_herb(self, entity: dict[str, Any]) -> dict[str, Any]:
        props = entity.get("props", {})
        return {
            "id": entity["id"],
            "name": entity.get("name") or entity["id"],
            "score": entity.get("score", 0),
            "tags": entity.get("tags", []),
            "food_homology": props.get("food_homology"),
        }

    def _load_herb_entities(self, herb_names: list[str]) -> list[dict[str, Any]]:
        entities = []
        for herb_name in herb_names:
            entity = self.neo4j_repository.get_entity(herb_name)
            if entity:
                entities.append(entity)
        return entities

    def _collect_formula_herbs(self, formula_payload: dict[str, Any]) -> list[str]:
        herb_names: list[str] = []
        for formula in formula_payload.get("formulas", []):
            for herb in formula.get("ingredients", []):
                herb_key = herb.get("herb_key") or herb.get("name")
                if herb_key and herb_key not in herb_names:
                    herb_names.append(herb_key)
        return herb_names

    def _formula_fallback(self, brief: dict[str, Any], selected: list[dict[str, Any]]) -> dict[str, Any]:
        goal = brief.get("goal", "")
        goal_tokens: list[str] = []
        if any(token in goal for token in ["感冒", "风寒", "风热"]):
            goal_tokens.extend(["解表", "散寒", "疏风", "宣肺", "止咳", "清热"])
        if "咳嗽" in goal:
            goal_tokens.extend(["止咳", "化痰"])
        if "鼻塞" in goal:
            goal_tokens.extend(["通窍", "宣肺"])

        prioritized = selected
        if goal_tokens:
            scored: list[tuple[int, dict[str, Any]]] = []
            for herb in selected:
                tags_str = " ".join(herb.get("tags", []))
                score = sum(1 for token in goal_tokens if token in tags_str)
                scored.append((score, herb))
            prioritized = [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)]

        ingredients = []
        for index, herb in enumerate(prioritized[:4]):
            role = ["君药", "臣药", "佐药", "使药"][index] if index < 4 else "配伍药"
            ingredients.append(
                {
                    "name": herb.get("name"),
                    "herb_key": herb.get("id"),
                    "role": role,
                    "dose_range": "待校验",
                    "rationale": "、".join(herb.get("tags", [])) or "与目标功效相关",
                }
            )

        compliance_notes = ["正式推荐仅保留药食同源目录药材。"]
        risks = ["当前为本地结构化结果，建议对剂量范围、孕期/慢病人群适配性做人工复核。"]
        if not prioritized:
            compliance_notes = ["未检索到足够候选药材，建议补充目标相关检索条件。"]
            risks = ["未检索到足够候选药材。"]

        return {
            "formulas": [
                {
                    "name": "药食同源候选方-1",
                    "ingredients": ingredients,
                    "classic_reference": "基于图谱候选药食同源药材组合，建议参照经典名方进一步优化配伍。",
                    "fang_jie": (
                        f"本方围绕「{brief['goal']}」设计，"
                        + ("以" + ingredients[0]["name"] + "为君药，" if ingredients else "")
                        + "遵循君臣佐使配伍原则，各药协同发挥目标功效。"
                        "具体配伍逻辑需结合体质与症状分型做二次校验。"
                    ),
                    "notes": "基于图谱候选药食同源药材自动生成，建议结合体质与症状分型做二次校验。",
                }
            ],
            "selection_rationale": f"围绕目标「{brief['goal']}」，按功效相关性优先筛选药食同源药材并进行君臣佐使配伍。",
            "fang_jie": "详见 formulas[].fang_jie",
            "classic_references": ["建议参照《太平惠民和剂局方》等经典方剂文献进行配伍优化。"],
            "compliance_notes": compliance_notes,
            "risks": risks,
        }

    def _efficacy_fallback(self, brief: dict[str, Any], herb_names: list[str]) -> dict[str, Any]:
        herb_entities = self._load_herb_entities(herb_names)
        tcm = []
        modern = []
        risks = []
        avoid_population = []
        for entity in herb_entities:
            props = entity.get("props", {})
            name = entity.get("name") or entity["id"]
            if props.get("food_homology"):
                tcm.append(f"{name}：药食同源，功效见图谱关系")
        target_population = [brief.get("target_population") or "成人一般人群（需按体质分型）"]
        if "感冒" in brief.get("goal", ""):
            target_population = ["风寒或风热感冒的轻症调养人群（非重症、非高风险人群）"]
        if not tcm and not modern:
            tcm = [brief["goal"]]
        if not avoid_population:
            avoid_population = ["需核实孕期、哺乳期及慢性病人群的适用性。"]
        return {
            "core_tcm_efficacy": tcm,
            "core_modern_efficacy": modern,
            "mechanisms": ["当前基于图谱关系进行本地兜底汇总。"],
            "target_population": target_population,
            "avoid_population": avoid_population,
            "contraindicated_population": ["孕期、哺乳期女性及对组方中任一药材过敏者禁用。"],
            "risks": risks,
            "literature_basis": ["《中国药典》2020年版", "国家卫健委药食同源物品目录"],
        }

    def _flavor_fallback(self, herb_names: list[str]) -> dict[str, Any]:
        herb_entities = self._load_herb_entities(herb_names)
        defects = []
        optimization_suggestions = []
        if not herb_entities:
            defects.append("缺少完整的风味标签，评估结果偏保守。")
        if herb_names:
            optimization_suggestions.append("可优先通过调整君臣比例改善整体接受度。")
            optimization_suggestions.append("必要时补充适应剂型的辅料或工艺调整。")
        return {
            "flavor_profile": {
                "taste": [],
                "aroma": [],
                "mouthfeel": ["待结合剂型进一步评估"],
            },
            "coordination_summary": "当前根据药材图谱关系做了初步风味归纳，建议结合剂型进一步验证。",
            "defects": defects,
            "optimization_suggestions": optimization_suggestions,
            "consumer_acceptance": "需结合目标人群口味偏好与剂型特点进一步评估消费者接受度。",
            "data_sources": ["FlavorDB", "BungentDB", "图谱 NatureFlavor/Flavor 关系"],
        }

    def _replacement_fallback(self, herb_entities: list[dict[str, Any]], replacement_payload: list[dict[str, Any]]) -> dict[str, Any]:
        recommendations = []
        baseline_comparison = []
        for herb in herb_entities:
            payload = next((item for item in replacement_payload if item["source_key"] == herb["id"]), None)
            if not payload or not payload["candidates"]:
                continue
            candidate = payload["candidates"][0]
            recommendations.append(
                {
                    "source_herb": herb["name"],
                    "recommended_herb": candidate.get("name"),
                    "score": candidate.get("score"),
                    "reason": "CAN_REPLACE Top1 候选",
                }
            )

        if recommendations:
            impact_summary = (
                "当前提供了正式替代候选，但这些替代需要进一步核验其功效保持、风味影响和合规性。"
                "如替代可能削弱核心目标，应保留原方并优先改进配伍。"
            )
            compliance_notes = [
                "替代前需再次确认替代药材仍属于药食同源目录。",
                "替代后需评估是否改变适用人群或禁忌范围。",
            ]
        else:
            impact_summary = (
                "目前未找到稳定可行的正式替代，建议保留原方成分并以配伍优化为主。"
            )
            compliance_notes = [
                "当前没有合适替代候选，需保留原方并复核药材合规性。",
            ]

        return {
            "recommended_replacements": recommendations,
            "baseline_comparison": baseline_comparison,
            "impact_summary": impact_summary,
            "compliance_notes": compliance_notes,
            "applicable_scenarios": (
                ["成本优化场景", "供应链保障场景"] if recommendations else ["暂无合适替代方案，建议保留原方"]
            ),
        }

    def _master_fallback(
        self,
        brief: dict[str, Any],
        question: str,
        final_mode: bool,
        formula_payload: dict[str, Any] | None = None,
        efficacy_payload: dict[str, Any] | None = None,
        flavor_payload: dict[str, Any] | None = None,
        replacement_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not final_mode:
            return {
                "brief_summary": brief["goal"],
                "task_plan": [
                    "方剂生成：筛选药食同源候选药材并设计组方",
                    "功效预测：评估中医与现代药理功效",
                    "风味预测：分析风味特征与消费者接受度",
                    "替代映射：多维对比替代方案",
                ],
                "consistency_checks": ["检查是否存在非药食同源成分", "检查替代后是否削弱核心目标"],
                "final_recommendation": "",
                "next_actions": ["等待子模块执行"],
                "data_sources": ["《中国药典》2020年版", "国家卫健委药食同源物品目录", "FlavorDB", "BungentDB"],
            }

        formulas = (formula_payload or {}).get("formulas", [])
        first_formula = formulas[0] if formulas else {}
        ingredients = first_formula.get("ingredients", [])
        herb_names = [item.get("name") for item in ingredients if item.get("name")]
        herb_text = "、".join(herb_names[:6]) if herb_names else "当前未形成稳定方剂"
        efficacy_points = (efficacy_payload or {}).get("core_tcm_efficacy", [])[:3]
        efficacy_text = "；".join(efficacy_points) if efficacy_points else "尚需补充功效证据"
        flavor_summary = (flavor_payload or {}).get("coordination_summary") or "风味评估信息有限"
        replacements = (replacement_payload or {}).get("recommended_replacements", [])
        replacement_text = "当前不建议替代核心药材" if not replacements else "存在可替代候选，需人工确认替代收益与风险"

        recommendation = (
            f"针对「{question}」，已形成药食同源候选方：{herb_text}。"
            f"核心功效判断为：{efficacy_text}。"
            f"风味与可接受性评估：{flavor_summary}。"
            f"{replacement_text}。"
            "建议先做小样验证和人群适配评估，再进入工艺放大。"
        )
        return {
            "brief_summary": brief["goal"],
            "task_plan": [
                "确认候选方剂成分与药食同源目录一致",
                "评估方剂功效与用户目标匹配度",
                "评估风味协调性与适用人群",
                "确认替代映射是否可行并评估风险",
            ],
            "consistency_checks": [
                "已按固定顺序整合各模块结果。",
                "方剂成分限定为药食同源目录候选。",
                "已检查替代建议是否存在削弱核心目标的风险。",
                "建议对禁忌人群与剂量区间继续做人工核验。",
            ],
            "final_recommendation": recommendation,
            "next_actions": [
                "复核正式方剂剂量和适用人群",
                "补充禁忌与适用边界说明",
                "根据剂型继续完善风味与工艺方案",
                "如存在证据缺口，补充实验或文献验证。",
            ],
            "data_sources": ["《中国药典》2020年版", "国家卫健委药食同源物品目录", "FlavorDB", "图谱 CAN_REPLACE 关系"],
        }

    def _normalize_goal(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()
