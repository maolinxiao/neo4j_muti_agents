import re

from app.services.qa_routing import QARoute, get_qa_route_resolver


class QuestionClassifier:
    SYMPTOM_HINTS = ("症", "病", "痛", "炎", "肿瘤", "综合征", "高血压", "糖尿病", "症状")
    FORMULA_HINTS = ("方", "方剂", "方子", "汤", "丸", "散", "颗粒", "胶囊", "饮")
    HERB_HINTS = ("功效", "作用", "禁忌", "适合", "药材", "食材", "药食同源", "性味", "归经")
    REPLACEMENT_HINTS = ("替换", "替代", "代替", "取代", "换成", "换掉", "药食同源化", "食品化", "改造成", "改造")
    CONSTITUTION_HINTS = ("体质", "量表", "问卷", "测试", "测评", "辨识", "识别")
    CONSTITUTION_TYPE_HINTS = ("平和质", "气虚质", "阳虚质", "阴虚质", "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质")
    PERSONAL_RISK_HINTS = ("孕妇", "儿童", "老人", "慢病", "过敏", "哺乳", "能不能吃", "可不可以吃", "能吃吗", "适合我吗")
    PRODUCT_HINTS = (
        "成药", "产品", "保健品", "口服液", "冲剂", "胶囊", "固体饮料", "代餐粉", "茶包",
        "软糖", "剂型", "工艺", "市场", "竞品", "好喝", "口味", "风味", "合规", "宣传",
        "标签", "GB2760", "GB7718", "普通食品",
    )
    PERSONAL_CONSTITUTION_HINTS = (
        "我适合吃什么",
        "我适合",
        "我能吃什么",
        "我可以吃",
        "适合吃",
        "我是什么体质",
        "帮我做体质测试",
        "帮我测试体质",
        "请给我测体质",
        "给我测体质",
        "我要测体质",
        "我想测体质",
        "我想重新测体质",
        "重新测体质",
        "重新测评",
        "重新测试",
        "再测一次体质",
        "再测体质",
        "标准量表测评",
        "我不确定自己的体质",
        "帮我做体质辨识",
        "帮我测体质",
    )

    def __init__(self) -> None:
        self.route_resolver = get_qa_route_resolver()

    def classify_route(self, question: str, fallback_question_type: str | None = None) -> QARoute:
        return self.route_resolver.resolve(question, fallback_question_type=fallback_question_type)

    def classify(self, question: str) -> str:
        route = self.classify_route(question)
        if route.task_key != "entity_explanation":
            return route.question_type
        if any(hint in question for hint in self.CONSTITUTION_TYPE_HINTS):
            return "constitution_recommendation"
        if any(hint in question for hint in self.REPLACEMENT_HINTS):
            return "formula_replacement"
        if any(hint in question for hint in self.PERSONAL_CONSTITUTION_HINTS):
            return "constitution_recommendation"
        if "体质" in question and any(hint in question for hint in ("不确定", "帮我测试", "测一测", "辨识")):
            return "constitution_recommendation"
        if any(hint in question for hint in self.CONSTITUTION_HINTS):
            return "constitution_recommendation"
        if any(hint in question for hint in self.PERSONAL_RISK_HINTS):
            return "constitution_recommendation"
        if any(hint in question for hint in self.PRODUCT_HINTS):
            return "product_recommendation"
        if any(hint in question for hint in self.SYMPTOM_HINTS):
            return "entity_explanation"
        if any(hint in question for hint in self.FORMULA_HINTS):
            return "formula_relation"
        if any(hint in question for hint in self.HERB_HINTS):
            return "herb_efficacy"
        if re.search(r"是什么|介绍|解释|含义", question):
            return "entity_explanation"
        return "entity_explanation"
