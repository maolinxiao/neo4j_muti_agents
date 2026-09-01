import json
import re
from time import perf_counter
from typing import Any

from app.repositories.neo4j_repository import Neo4jRepository
from app.repositories.postgres_repository import PostgresRepository
from app.services.deepseek_client import DeepSeekClient


class RnDWorkflowOrchestrator:
    AGENT_SEQUENCE = [
        "master_control",
        "formula_generation",
        "efficacy_prediction",
        "flavor_prediction",
        "replacement_mapping",
        "master_control_final",
    ]

    ROLE_DUTY = {
        "君药": "针对目标需求与核心功效起主导作用",
        "臣药": "辅助君药增强功效或针对兼证",
        "佐药": "佐助主药或制约偏性，平衡药性与口感",
        "使药": "调和诸药、改善整体协调性",
        "配伍药": "协同配方整体目标，起辅助配伍作用",
    }

    def __init__(
        self,
        postgres_repository: PostgresRepository,
        neo4j_repository: Neo4jRepository,
        llm_client: DeepSeekClient,
    ) -> None:
        self.postgres_repository = postgres_repository
        self.neo4j_repository = neo4j_repository
        self.llm_client = llm_client

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
                        "按企业端研发逻辑拆解需求并输出可执行任务计划。"
                        "若命中经典名方或方剂药食同源化任务，必须先读 KB5 原方，再按 KB1 逐味合法性判断、"
                        "KB4 动态单味替代、KB2/KB3 功效风味复核、KB7 合规边界推进。"
                        "产品开发任务按 KB1、KB2、KB3、KB6、KB7 推进，风味/剂型要先判断好喝、可做、合规。"
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
                        "整合前序模块（方剂生成、功效预测、风味预测、替代映射）并输出「交付研发负责人的总结报告」。"
                        "报告必须包含：最终配方（组成、君臣佐使角色、建议剂量区间、作用与剂量依据、方解一句）、"
                        "君臣佐使一览、KB5 原方依据（含保留/替换/新增/删除逐味标注，替换引用 KB4 CAN_REPLACE 评分与系统综合可信度）、"
                        "功效与机制摘要、风味与适配、替代对比要点、合规与风险、证据不足与下一步。"
                        "禁止只复述前序模块内容；所有输出需标注数据来源。若证据不足，需具体说明缺口和补充数据建议。"
                    ),
                },
                final_master_fallback,
                max_completion_tokens=1800,
            )

            steps = self.postgres_repository.list_workflow_step_runs(run.id)
            final_report = self._assemble_final_report(
                final_master["output_payload"],
                formula_result["output_payload"],
                efficacy_result["output_payload"],
                flavor_result["output_payload"],
                replacement_result["output_payload"],
            )
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
                "task_plan": [],
                "data_sources": [],
                "final_formula": {"name": "", "composition": []},
                "monarch_minister_summary": [],
                "original_formula": {
                    "name": "",
                    "source": "",
                    "changes": {"retained": [], "replaced": [], "added": [], "removed": []},
                },
                "efficacy_summary": {"effects": [], "mechanisms": []},
                "flavor_summary": {"notes": [], "acceptance": ""},
                "compliance_risks": [],
                "evidence_gaps": [],
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
        formula_contexts = self.neo4j_repository.find_formulas_for_brief(search_terms, limit=3)
        candidates = self.neo4j_repository.find_candidate_herbs_for_brief(search_terms, limit=18)
        selected = candidates[:8]
        herb_names = self._formula_context_herb_names(formula_contexts) + [item["id"] for item in selected]
        herb_names = list(dict.fromkeys([name for name in herb_names if name]))
        graph_snapshot_id = self._save_graph_snapshot(workflow_session_id, brief["goal"], herb_names) if herb_names else None
        payload = {
            "brief": brief,
            "kb5_formula_context": formula_contexts,
            "candidate_herbs": [self._compact_herb(item) for item in candidates],
            "instruction": (
                "若 kb5_formula_context 非空，必须先保留 KB5 原方来源、组成、君臣佐使、功效、主治、禁忌和剂量比例，"
                "再逐味判断药食同源合法性：药食同源药材保留，非药食同源药材进入后续 KB4 单味替代流程，"
                "有明显安全风险的药材只作原方说明或建议剔除。"
                "若未命中 KB5 原方，则从候选药食同源药材中设计 1-3 个候选方剂。每个方剂需输出："
                "方名、配伍（君臣佐使）、各药材剂量区间（标注成人每日推荐用量与最大安全用量）、"
                "方解（配伍逻辑与各药材作用）、经典名方参考、适用场景、不适用场景。"
                "所有药材须来自药食同源目录，剂量须符合食品安全标准。"
            ),
        }
        fallback = self._formula_fallback(brief, selected, formula_contexts)
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
            "target_population": brief.get("target_population") or "未指定，需按体质/场景补充",
            "population_profile": self._build_rnd_population_profile(brief, efficacy_result["output_payload"]),
            "candidate_flavor_population_matrix": self._build_replacement_matrix(herb_entities, replacement_payload),
            "instruction": (
                "只基于 KB4 CAN_REPLACE 单味药替代评分给出替代建议，不能声称存在预生成方剂替代版本。"
                "基于功效、风味、目标人群/体质、成本、合规、工艺、供应链七个维度，给出正式替代建议。"
                "必须对比替代前后的功效等效性、风味影响、目标人群变化、成本变动、工艺适配性差异。"
                "优先推荐供应稳定、成本更低、风味更优的药食同源替代品种。"
                "如果候选风味接受度低、风味相似度低或安全/人群边界变窄，必须降级推荐或反对替代。"
                "若无可替代项，需明确说明「为什么不建议替代」并标注适用场景。"
            ),
        }
        fallback = self._replacement_fallback(
            herb_entities,
            replacement_payload,
            brief=brief,
            efficacy_payload=efficacy_result["output_payload"],
            flavor_payload=flavor_result["output_payload"],
        )
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
        max_completion_tokens: int = 1000,
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
        output_payload, latency_ms = self.llm_client.generate_structured_output(
            system_prompt=system_prompt,
            payload=input_payload,
            fallback=fallback,
            output_schema=prompt.output_schema if prompt else None,
            required_keys=list(fallback.keys()),
            agent_key=agent_key,
            max_completion_tokens=max_completion_tokens,
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
        brief = self.llm_client.build_rnd_brief(question)
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

    def _build_rnd_population_profile(self, brief: dict[str, Any], efficacy_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        efficacy_payload = efficacy_payload or {}
        return {
            "target_population": brief.get("target_population") or efficacy_payload.get("target_population") or "未指定",
            "avoid_population": efficacy_payload.get("avoid_population", []),
            "contraindicated_population": efficacy_payload.get("contraindicated_population", []),
            "dosage_form": brief.get("dosage_form") or "未指定",
            "constraints": brief.get("constraints", []),
            "note": "替代映射需要检查替代后是否改变适用人群、禁忌人群或口味接受度。",
        }

    def _build_replacement_matrix(
        self,
        herb_entities: list[dict[str, Any]],
        replacement_payload: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for herb in herb_entities:
            payload = next((item for item in replacement_payload if item["source_key"] == herb["id"]), None)
            if not payload:
                continue
            source_snapshot = self._herb_flavor_snapshot(herb)
            for candidate in payload.get("candidates", [])[:5]:
                rows.append(
                    {
                        "source_herb": herb.get("name") or herb["id"],
                        "candidate_herb": candidate.get("name") or candidate.get("id"),
                        "final_score": candidate.get("score"),
                        "professional_score": candidate.get("professional_score"),
                        "flavor_acceptance": candidate.get("flavor_acceptance"),
                        "flavor_similarity": candidate.get("flavor_similarity"),
                        "safety_score": candidate.get("safety_score"),
                        "source_flavor": source_snapshot,
                        "candidate_flavor": self._herb_flavor_snapshot(candidate),
                        "population_fit_note": self._population_fit_note(candidate),
                    }
                )
        return rows[:40]

    @staticmethod
    def _herb_flavor_snapshot(entity: dict[str, Any]) -> dict[str, Any]:
        props = entity.get("props", {}) or {}
        return {
            "nature": props.get("nature"),
            "flavor": props.get("flavor"),
            "overall_flavor_acceptance": props.get("overall_flavor_acceptance"),
            "bitter_risk": props.get("bitter_risk"),
            "astringent_risk": props.get("astringent_risk"),
            "herbal_medicine_risk": props.get("herbal_medicine_risk"),
            "aftertaste_risk": props.get("aftertaste_risk"),
            "aroma_description": props.get("aroma_description"),
            "usage_precautions": props.get("usage_precautions") or props.get("usage_note"),
            "contraindication": props.get("contraindication"),
            "food_homology": props.get("food_homology") or props.get("is_food_homology"),
        }

    @staticmethod
    def _format_flavor_snapshot(snapshot: dict[str, Any]) -> str:
        parts: list[str] = []
        for key, label in [
            ("flavor", "味"),
            ("nature", "性"),
            ("aroma_description", "香气"),
            ("overall_flavor_acceptance", "接受度"),
            ("bitter_risk", "苦味风险"),
            ("astringent_risk", "涩感风险"),
            ("herbal_medicine_risk", "药味风险"),
            ("aftertaste_risk", "后味风险"),
        ]:
            value = snapshot.get(key)
            if value is not None and value != "":
                parts.append(f"{label}:{value}")
        return "；".join(parts) if parts else "建议通过感官小试确认风味特征"

    @staticmethod
    def _population_fit_note(entity: dict[str, Any]) -> str:
        props = entity.get("props", {}) or {}
        cautions = [
            props.get("contraindication"),
            props.get("usage_precautions"),
            props.get("usage_note"),
            props.get("pregnancy_taboo"),
        ]
        caution_text = "；".join(str(item) for item in cautions if item)
        if caution_text:
            return f"需复核人群边界：{caution_text}"
        return "未见明确人群禁忌字段，仍需按目标人群/体质复核。"

    def _compact_herb(self, entity: dict[str, Any]) -> dict[str, Any]:
        props = entity.get("props", {})
        return {
            "id": entity["id"],
            "name": entity.get("name") or entity["id"],
            "score": entity.get("score", 0),
            "tags": entity.get("tags", []),
            "food_homology": props.get("food_homology"),
            "nature": props.get("nature"),
            "flavor": props.get("flavor"),
            "overall_flavor_acceptance": props.get("overall_flavor_acceptance"),
            "bitter_risk": props.get("bitter_risk"),
            "astringent_risk": props.get("astringent_risk"),
            "herbal_medicine_risk": props.get("herbal_medicine_risk"),
            "aroma_description": props.get("aroma_description"),
            "usage_precautions": props.get("usage_precautions") or props.get("usage_note"),
            "contraindication": props.get("contraindication"),
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
        for formula_context in formula_payload.get("kb5_formula_context", []):
            for ingredient in formula_context.get("ingredients", []):
                herb_name = ingredient.get("name")
                if herb_name and herb_name not in herb_names:
                    herb_names.append(herb_name)
        for formula in formula_payload.get("formulas", []):
            for herb in formula.get("ingredients", []):
                herb_key = herb.get("herb_key") or herb.get("name")
                if herb_key and herb_key not in herb_names:
                    herb_names.append(herb_key)
        return herb_names

    @staticmethod
    def _formula_context_herb_names(formula_contexts: list[dict[str, Any]]) -> list[str]:
        herb_names: list[str] = []
        for formula_context in formula_contexts:
            for ingredient in formula_context.get("ingredients", []):
                herb_name = ingredient.get("name")
                if herb_name and herb_name not in herb_names:
                    herb_names.append(herb_name)
        return herb_names

    def _formula_fallback(
        self,
        brief: dict[str, Any],
        selected: list[dict[str, Any]],
        formula_contexts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        goal = brief.get("goal", "")
        formula_contexts = formula_contexts or []
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

        original_formula = formula_contexts[0] if formula_contexts else None
        ingredients = []
        if original_formula:
            for index, herb in enumerate(original_formula.get("ingredients", [])[:4]):
                role = herb.get("role") or (["君药", "臣药", "佐药", "使药"][index] if index < 4 else "配伍药")
                ingredients.append(
                    {
                        "name": herb.get("name"),
                        "herb_key": herb.get("name"),
                        "role": role,
                        "dose_range": herb.get("dosage") or "剂量待结合原方出处与专业规范核定",
                        "rationale": "KB5 原方组成，需经 KB1 合法性判断和 KB4 单味替代复核",
                    }
                )

        for index, herb in enumerate(prioritized[: max(0, 4 - len(ingredients))]):
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

        compliance_notes = [
            "正式推荐仅保留药食同源目录药材。",
            "若命中 KB5 原方，原方中非药食同源药材需进入 KB4 单味替代评分，不能直接食品化。",
        ]
        risks = ["当前为本地结构化结果，建议对剂量范围、孕期/慢病人群适配性做人工复核。"]
        if not prioritized:
            compliance_notes = ["未检索到足够候选药材，建议补充目标相关检索条件。"]
            risks = ["未检索到足够候选药材。"]

        return {
            "kb5_formula_context": formula_contexts,
            "formulas": [
                {
                    "name": (
                        f"{original_formula.get('formula_name')}药食同源化候选方"
                        if original_formula
                        else "药食同源候选方-1"
                    ),
                    "ingredients": ingredients,
                    "classic_reference": (
                        f"KB5 原方：{original_formula.get('formula_name')}；来源：{'、'.join(original_formula.get('sources', [])) or '建议在定稿前核对原方文献'}。"
                        if original_formula
                        else "基于图谱候选药食同源药材组合，建议参照经典名方进一步优化配伍。"
                    ),
                    "fang_jie": (
                        "先保留 KB5 原方语境，再按 KB1 合法性和 KB4 单味替代评分动态重组，需专家复核君臣佐使与剂量。"
                        if original_formula
                        else (
                            f"本方围绕「{brief['goal']}」设计，"
                            + ("以" + ingredients[0]["name"] + "为君药，" if ingredients else "")
                            + "遵循君臣佐使配伍原则，各药协同发挥目标功效。"
                            "具体配伍逻辑需结合体质与症状分型做二次校验。"
                        )
                    ),
                    "notes": (
                        "KB5 原方单独保留；当前不是预生成替代方，而是原方依据 + 后续 KB4 单味替代的动态重组建议。"
                        if original_formula
                        else "基于图谱候选药食同源药材自动生成，建议结合体质与症状分型做二次校验。"
                    ),
                }
            ],
            "selection_rationale": (
                f"已命中 KB5 原方「{original_formula.get('formula_name')}」，先保留原方依据，再逐味进入合法性与替代分流。"
                if original_formula
                else f"围绕目标「{brief['goal']}」，按功效相关性优先筛选药食同源药材并进行君臣佐使配伍。"
            ),
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
        tastes: list[str] = []
        aromas: list[str] = []
        mouthfeel: list[str] = []
        risk_notes: list[str] = []
        for entity in herb_entities:
            name = entity.get("name") or entity["id"]
            snapshot = self._herb_flavor_snapshot(entity)
            if snapshot.get("flavor"):
                tastes.append(f"{name}:{snapshot['flavor']}")
            if snapshot.get("aroma_description"):
                aromas.append(f"{name}:{snapshot['aroma_description']}")
            for key, label in [
                ("bitter_risk", "苦味"),
                ("astringent_risk", "涩感"),
                ("herbal_medicine_risk", "药味"),
                ("aftertaste_risk", "后味"),
            ]:
                value = snapshot.get(key)
                if value is not None and value != "":
                    mouthfeel.append(f"{name}:{label}{value}")
                    try:
                        if float(value) >= 0.6:
                            risk_notes.append(f"{name}{label}风险偏高")
                    except (TypeError, ValueError):
                        pass
        if not herb_entities:
            defects.append("缺少完整的风味标签，评估结果偏保守。")
        if risk_notes:
            defects.extend(risk_notes[:6])
        if herb_names:
            optimization_suggestions.append("可优先通过调整君臣比例改善整体接受度。")
            optimization_suggestions.append("必要时补充适应剂型的辅料或工艺调整。")
        return {
            "flavor_profile": {
                "taste": tastes[:10],
                "aroma": aromas[:10],
                "mouthfeel": mouthfeel[:10] or ["待结合剂型进一步评估"],
            },
            "coordination_summary": (
                "当前根据药材图谱 KB3 风味属性做了初步风味归纳，建议结合剂型和目标人群口味偏好进一步验证。"
            ),
            "defects": defects,
            "optimization_suggestions": optimization_suggestions,
            "consumer_acceptance": "需结合目标人群口味偏好与剂型特点进一步评估消费者接受度。",
            "data_sources": ["FlavorDB", "BungentDB", "图谱 NatureFlavor/Flavor 关系"],
        }

    def _replacement_fallback(
        self,
        herb_entities: list[dict[str, Any]],
        replacement_payload: list[dict[str, Any]],
        brief: dict[str, Any] | None = None,
        efficacy_payload: dict[str, Any] | None = None,
        flavor_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        brief = brief or {}
        population_profile = self._build_rnd_population_profile(brief, efficacy_payload or {})
        recommendations = []
        baseline_comparison = []
        for herb in herb_entities:
            payload = next((item for item in replacement_payload if item["source_key"] == herb["id"]), None)
            if not payload or not payload["candidates"]:
                continue
            candidate = payload["candidates"][0]
            source_flavor = self._herb_flavor_snapshot(herb)
            candidate_flavor = self._herb_flavor_snapshot(candidate)
            flavor_acceptance = candidate.get("flavor_acceptance")
            flavor_similarity = candidate.get("flavor_similarity")
            safety_score = candidate.get("safety_score")
            population_note = self._population_fit_note(candidate)
            downgrade_reasons = []
            for value, label in [
                (flavor_acceptance, "风味接受度偏低"),
                (safety_score, "安全评分偏低"),
            ]:
                try:
                    if value is not None and float(value) < 0.6:
                        downgrade_reasons.append(label)
                except (TypeError, ValueError):
                    pass
            if candidate.get("recommendation_status") and "不" in str(candidate.get("recommendation_status")):
                downgrade_reasons.append(f"推荐状态：{candidate.get('recommendation_status')}")
            reason_parts = [
                "CAN_REPLACE Top1 候选",
                f"风味接受度 {flavor_acceptance}" if flavor_acceptance is not None else "缺少风味接受度",
                f"风味相似度 {flavor_similarity}" if flavor_similarity is not None else "缺少风味相似度",
                population_note,
            ]
            if downgrade_reasons:
                reason_parts.append("需降级复核：" + "、".join(downgrade_reasons))
            recommendations.append(
                {
                    "source_herb": herb["name"],
                    "recommended_herb": candidate.get("name"),
                    "score": candidate.get("score"),
                    "professional_score": candidate.get("professional_score"),
                    "flavor_acceptance": flavor_acceptance,
                    "flavor_similarity": flavor_similarity,
                    "safety_score": safety_score,
                    "flavor_impact": (
                        f"原药材：{self._format_flavor_snapshot(source_flavor)}；"
                        f"替代药材：{self._format_flavor_snapshot(candidate_flavor)}"
                    ),
                    "population_fit": population_note,
                    "target_population": population_profile.get("target_population"),
                    "recommendation_status": candidate.get("recommendation_status") or ("需复核" if downgrade_reasons else "可作为候选"),
                    "reason": "；".join(reason_parts),
                }
            )
            baseline_comparison.append(
                {
                    "source_herb": herb["name"],
                    "candidate_herb": candidate.get("name"),
                    "efficacy_score": candidate.get("professional_score") or candidate.get("effect_similarity"),
                    "flavor_before": self._format_flavor_snapshot(source_flavor),
                    "flavor_after": self._format_flavor_snapshot(candidate_flavor),
                    "flavor_acceptance": flavor_acceptance,
                    "flavor_similarity": flavor_similarity,
                    "safety_score": safety_score,
                    "population_before_after": population_note,
                    "decision": "降级复核" if downgrade_reasons else "候选保留",
                }
            )

        if recommendations:
            target_population = population_profile.get("target_population") or "未指定目标人群"
            flavor_summary = (flavor_payload or {}).get("coordination_summary") or "风味预测信息有限"
            impact_summary = (
                f"当前提供了正式替代候选，已按目标人群（{target_population}）、风味接受度、风味相似度和安全性做初步筛查。"
                f"风味模块结论：{flavor_summary}。"
                "这些替代仍需要进一步核验其功效保持、风味影响、人群边界和合规性。"
                "如替代可能削弱核心目标，应保留原方并优先改进配伍。"
            )
            compliance_notes = [
                "替代前需再次确认替代药材仍属于药食同源目录。",
                "替代后需评估是否改变适用人群或禁忌范围。",
                "风味接受度低或目标人群不明确时，不应直接进入最终配方。",
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
                ["风味优化场景", "目标人群适配场景", "成本优化场景", "供应链保障场景"] if recommendations else ["暂无合适替代方案，建议保留原方"]
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
                    "方剂生成：先检索 KB5 名方/方剂原方，再筛选药食同源候选药材并设计食品化组方",
                    "功效预测：结合 KB2 评估中医与现代药理功效",
                    "风味预测：结合 KB3/KB6 判断好喝程度、剂型适配和消费者接受度",
                    "替代映射：仅基于 KB4 单味药 CAN_REPLACE 关系做动态替代对比",
                    "合规审查：用 KB1/KB7 检查原料合法性、普通食品宣传边界和风险人群",
                ],
                "consistency_checks": [
                    "检查是否存在非药食同源成分",
                    "检查 KB5 原方语境是否保留",
                    "检查替代后是否削弱核心目标",
                    "检查风味剂型和食品化合规边界是否完整",
                ],
                "final_recommendation": "",
                "next_actions": ["等待子模块执行"],
                "data_sources": ["KB1 药食同源合法性", "KB2 功效病症性味归经", "KB3 风味评价", "KB4 单味替代评分", "KB5 名方方剂", "KB6 产品市场", "KB7 食品合规"],
            }

        formulas = (formula_payload or {}).get("formulas", [])
        first_formula = formulas[0] if formulas else {}
        kb5_contexts = (formula_payload or {}).get("kb5_formula_context", [])
        kb5_context = kb5_contexts[0] if kb5_contexts else None

        composition = self._composition_from_formula(formula_payload)
        herb_names = [item["name"] for item in composition]
        herb_text = "、".join(herb_names[:6]) if herb_names else "当前未形成稳定方剂"
        efficacy_points = (efficacy_payload or {}).get("core_tcm_efficacy", [])[:3] or []
        efficacy_text = "；".join(str(item) for item in efficacy_points) if efficacy_points else "尚需补充功效证据"
        flavor_section = self._flavor_summary_section(None, flavor_payload)
        replacements = (replacement_payload or {}).get("recommended_replacements", []) or []
        replacement_text = "当前不建议替代核心药材" if not replacements else "存在可替代候选，需人工确认替代收益与风险"
        kb5_text = ""
        if kb5_context:
            kb5_text = (
                f"KB5 原方依据：{kb5_context.get('formula_name')}；"
                f"来源：{'、'.join(kb5_context.get('sources', [])) or '建议在定稿前核对原方文献'}。"
            )

        recommendation = (
            f"针对「{question}」，已形成药食同源候选方：{herb_text}。\n"
            f"{kb5_text}\n"
            f"核心功效判断为：{efficacy_text}。\n"
            f"风味与可接受性评估：{flavor_section.get('acceptance') or '风味评估信息有限'}。\n"
            f"{replacement_text}。\n"
            "详细组成、君臣佐使、原方依据、替代对比、合规风险与证据缺口见结构化字段；\n"
            "建议先做小样验证、感官评价、稳定性和合规文案复核，再进入工艺放大。"
        )
        return {
            "brief_summary": brief["goal"],
            "task_plan": [
                "确认 KB5 原方依据、组成和君臣佐使是否已保留",
                "用 KB1 确认候选方剂成分与药食同源目录一致",
                "用 KB2 评估方剂功效与用户目标匹配度",
                "用 KB3/KB6 评估风味协调性、剂型和适用人群",
                "用 KB4 确认单味替代映射是否可行并评估风险",
                "用 KB7 复核普通食品宣传边界和上市风险",
            ],
            "consistency_checks": [
                "已按固定顺序整合各模块结果。",
                "KB5 名方/方剂知识库单独保留，未将 KB4 误用为方剂替代版本库。",
                "方剂成分需限定为药食同源目录候选，非药食同源原方药材必须走 KB4 单味替代。",
                "已检查替代建议是否存在削弱核心目标的风险。",
                "建议对禁忌人群、剂量区间、风味剂型和合规文案继续做人工核验。",
            ],
            "final_recommendation": recommendation,
            "next_actions": [
                "复核 KB5 原方组成、剂量比例和适用人群",
                "列出保留药材、替代药材和不能完全替代点",
                "补充禁忌、普通食品宣传边界和适用边界说明",
                "根据剂型继续完善风味、工艺和小样验证方案",
                "如存在证据缺口，补充实验或文献验证。",
            ],
            "data_sources": ["KB1 药食同源合法性", "KB2 功效病症性味归经", "KB3 风味评价", "KB4 CAN_REPLACE 单味替代", "KB5 名方/方剂", "KB6 产品市场", "KB7 食品合规"],
            "final_formula": self._final_formula_section(None, formula_payload),
            "monarch_minister_summary": self._monarch_minister_summary(None, formula_payload),
            "original_formula": self._original_formula_section(None, formula_payload, replacement_payload),
            "efficacy_summary": self._efficacy_summary_section(None, efficacy_payload),
            "flavor_summary": flavor_section,
            "compliance_risks": self._collect_compliance_risks(formula_payload, efficacy_payload, replacement_payload),
            "evidence_gaps": self._collect_evidence_gaps(formula_payload, efficacy_payload, flavor_payload, replacement_payload),
        }

    def _assemble_final_report(
        self,
        final_output: dict[str, Any],
        formula_payload: dict[str, Any] | None,
        efficacy_payload: dict[str, Any] | None,
        flavor_payload: dict[str, Any] | None,
        replacement_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """组装最终报告：旧键保持兼容；结构化键优先取主控输出，缺失/为空时按模块 payload 抽取。"""
        return {
            "brief_summary": final_output.get("brief_summary") or "",
            "final_recommendation": final_output.get("final_recommendation") or "",
            "consistency_checks": final_output.get("consistency_checks") or [],
            "next_actions": final_output.get("next_actions") or [],
            "task_plan": final_output.get("task_plan") or [],
            "data_sources": final_output.get("data_sources") or [],
            "final_formula": self._final_formula_section(final_output.get("final_formula"), formula_payload),
            "monarch_minister_summary": self._monarch_minister_summary(
                final_output.get("monarch_minister_summary"), formula_payload
            ),
            "original_formula": self._original_formula_section(
                final_output.get("original_formula"), formula_payload, replacement_payload
            ),
            "efficacy_summary": self._efficacy_summary_section(final_output.get("efficacy_summary"), efficacy_payload),
            "flavor_summary": self._flavor_summary_section(final_output.get("flavor_summary"), flavor_payload),
            "compliance_risks": (
                final_output.get("compliance_risks")
                or self._collect_compliance_risks(formula_payload, efficacy_payload, replacement_payload)
            ),
            "evidence_gaps": (
                final_output.get("evidence_gaps")
                or self._collect_evidence_gaps(formula_payload, efficacy_payload, flavor_payload, replacement_payload)
            ),
            "modules": {
                "formula_generation": formula_payload,
                "efficacy_prediction": efficacy_payload,
                "flavor_prediction": flavor_payload,
                "replacement_mapping": replacement_payload,
            },
        }

    @staticmethod
    def _dedup(items: list[Any]) -> list[Any]:
        seen: set[str] = set()
        result: list[Any] = []
        for item in items:
            key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    @staticmethod
    def _composition_from_formula(formula_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
        formula_payload = formula_payload or {}
        kb5_contexts = formula_payload.get("kb5_formula_context", []) or []
        kb5_context = kb5_contexts[0] if kb5_contexts else None
        source = f"KB5 原方「{kb5_context.get('formula_name')}」" if kb5_context else "药食同源候选组方（图谱候选药材）"
        composition: list[dict[str, Any]] = []
        formulas = formula_payload.get("formulas", []) or []
        for formula in formulas[:1]:
            for item in formula.get("ingredients", []) or []:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("herb_key")
                if not name:
                    continue
                composition.append(
                    {
                        "name": name,
                        "role": item.get("role") or "配伍药",
                        "dose": item.get("dose_range") or item.get("dose") or "待校验",
                        "rationale": (
                            item.get("rationale")
                            or item.get("dose_rationale")
                            or item.get("fang_jie_role")
                            or "与目标功效相关"
                        ),
                        "basis": item.get("basis") or item.get("evidence") or "",
                        "source": item.get("source") or source,
                    }
                )
        return composition

    def _final_formula_section(self, value: Any, formula_payload: dict[str, Any] | None) -> dict[str, Any]:
        formulas = (formula_payload or {}).get("formulas", []) or []
        first_formula = formulas[0] if formulas else {}
        kb5_contexts = (formula_payload or {}).get("kb5_formula_context", []) or []
        kb5_context = kb5_contexts[0] if kb5_contexts else None
        extracted_name = first_formula.get("name") or (
            f"{kb5_context.get('formula_name')}药食同源化候选方" if kb5_context else "药食同源候选方（待定名）"
        )
        extracted_composition = self._composition_from_formula(formula_payload)
        if isinstance(value, dict):
            composition = value.get("composition")
            if isinstance(composition, list) and composition:
                return value
            return {"name": value.get("name") or extracted_name, "composition": extracted_composition}
        return {"name": extracted_name, "composition": extracted_composition}

    def _monarch_minister_summary(
        self, value: Any, formula_payload: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        if isinstance(value, list) and value:
            return value
        composition = self._composition_from_formula(formula_payload)
        grouped: dict[str, list[str]] = {}
        for item in composition:
            role = item.get("role") or "配伍药"
            grouped.setdefault(role, []).append(item["name"])
        return [
            {
                "role": role,
                "herbs": names,
                "duty": self.ROLE_DUTY.get(role, "协同配伍，辅助整体目标"),
            }
            for role, names in grouped.items()
        ]

    def _original_formula_section(
        self,
        value: Any,
        formula_payload: dict[str, Any] | None,
        replacement_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if isinstance(value, dict):
            changes = value.get("changes") if isinstance(value.get("changes"), dict) else {}
            if value.get("name") or any(changes.values()):
                return {"name": value.get("name", ""), "source": value.get("source", ""), "changes": changes}
        kb5_contexts = (formula_payload or {}).get("kb5_formula_context", []) or []
        kb5_context = kb5_contexts[0] if kb5_contexts else None
        composition = self._composition_from_formula(formula_payload)
        comp_names = [item["name"] for item in composition]
        kb5_names = [item.get("name") for item in (kb5_context or {}).get("ingredients", []) or [] if item.get("name")]
        kb5_names = list(dict.fromkeys(kb5_names))
        replacements = (replacement_payload or {}).get("recommended_replacements", []) or []
        replaced: list[dict[str, Any]] = []
        replaced_sources: set[str] = set()
        replaced_targets: set[str] = set()
        for item in replacements:
            if not isinstance(item, dict):
                continue
            frm = item.get("source_herb")
            to = item.get("recommended_herb")
            if frm and to:
                replaced.append(
                    {
                        "from": frm,
                        "to": to,
                        "score": item.get("score"),
                        "confidence": item.get("professional_score") or item.get("confidence") or "待复核",
                    }
                )
                replaced_sources.add(frm)
                replaced_targets.add(to)
        retained = [name for name in comp_names if name in kb5_names and name not in replaced_sources]
        added = [name for name in comp_names if name and name not in kb5_names and name not in replaced_targets]
        removed = [name for name in kb5_names if name not in comp_names]
        return {
            "name": kb5_context.get("formula_name") if kb5_context else "",
            "source": "、".join(kb5_context.get("sources", [])) if kb5_context and kb5_context.get("sources") else "",
            "changes": {"retained": retained, "replaced": replaced, "added": added, "removed": removed},
        }

    @staticmethod
    def _efficacy_summary_section(value: Any, efficacy_payload: dict[str, Any] | None) -> dict[str, Any]:
        if isinstance(value, dict) and (value.get("effects") or value.get("mechanisms")):
            return value
        efficacy_payload = efficacy_payload or {}
        effects = RnDWorkflowOrchestrator._dedup(
            [item for item in (efficacy_payload.get("core_tcm_efficacy", []) or [])]
            + [item for item in (efficacy_payload.get("core_modern_efficacy", []) or [])]
        )
        mechanisms = RnDWorkflowOrchestrator._dedup(efficacy_payload.get("mechanisms", []) or [])
        return {"effects": effects, "mechanisms": mechanisms}

    @staticmethod
    def _flavor_summary_section(value: Any, flavor_payload: dict[str, Any] | None) -> dict[str, Any]:
        if isinstance(value, dict) and (value.get("notes") or value.get("acceptance")):
            return value
        flavor_payload = flavor_payload or {}
        profile = flavor_payload.get("flavor_profile", {}) or {}
        notes: list[str] = []
        if profile.get("taste"):
            notes.append("味觉：" + "；".join(str(item) for item in profile["taste"]))
        if profile.get("aroma"):
            notes.append("香气：" + "；".join(str(item) for item in profile["aroma"]))
        if profile.get("mouthfeel"):
            notes.append("口感：" + "；".join(str(item) for item in profile["mouthfeel"]))
        notes.extend(str(item) for item in (flavor_payload.get("defects", []) or []) if item)
        if flavor_payload.get("coordination_summary"):
            notes.append(str(flavor_payload["coordination_summary"]))
        return {
            "notes": RnDWorkflowOrchestrator._dedup(notes),
            "acceptance": flavor_payload.get("consumer_acceptance") or "需结合目标人群口味偏好与剂型做感官小试验证",
        }

    @staticmethod
    def _collect_compliance_risks(
        formula_payload: dict[str, Any] | None,
        efficacy_payload: dict[str, Any] | None,
        replacement_payload: dict[str, Any] | None,
    ) -> list[str]:
        risks: list[str] = []
        for payload in (formula_payload, replacement_payload):
            if not isinstance(payload, dict):
                continue
            for key in ("compliance_notes", "risks"):
                for item in payload.get(key, []) or []:
                    if isinstance(item, str) and item and item not in risks:
                        risks.append(item)
        efficacy_payload = efficacy_payload or {}
        for item in efficacy_payload.get("risks", []) or []:
            if isinstance(item, str) and item and item not in risks:
                risks.append(item)
        for key, label in (("avoid_population", "不适宜人群"), ("contraindicated_population", "禁忌人群")):
            for item in efficacy_payload.get(key, []) or []:
                if not item:
                    continue
                text = f"{label}：{item}" if isinstance(item, str) else label
                if text not in risks:
                    risks.append(text)
        return risks

    @staticmethod
    def _collect_evidence_gaps(
        formula_payload: dict[str, Any] | None,
        efficacy_payload: dict[str, Any] | None,
        flavor_payload: dict[str, Any] | None,
        replacement_payload: dict[str, Any] | None,
    ) -> list[str]:
        gaps: list[str] = []
        formulas = (formula_payload or {}).get("formulas", []) or []
        if not formulas:
            gaps.append("当前未形成稳定方剂，需补充目标功效、适用人群、剂型等需求信息。")
        else:
            gaps.append("剂量区间与配伍逻辑需经中药/食品专业复核，并进行小样感官与稳定性验证。")
        replacements = (replacement_payload or {}).get("recommended_replacements", []) or []
        if replacements:
            gaps.append("替代项的收益与风险（功效保持、人群边界、合规性）需进一步核验后再进入定稿。")
        elif formulas:
            gaps.append("暂未获得稳定替代候选，建议保留原方并以配伍优化为主。")
        gaps.append("风味与接受度结论需结合目标人群口味偏好与剂型做感官小试验证。")
        return RnDWorkflowOrchestrator._dedup(gaps)

    def _normalize_goal(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()
