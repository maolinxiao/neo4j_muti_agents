import re


class QuestionClassifier:
    SYMPTOM_HINTS = ("病", "症", "炎", "癌", "肿瘤", "综合征", "高血压", "糖尿病", "症状")
    FORMULA_HINTS = ("方", "方剂", "方子", "汤", "丸", "散", "颗粒", "胶囊", "饮")
    HERB_HINTS = ("功效", "作用", "禁忌", "适合", "药材", "食材", "药食同源", "性味", "归经")
    REPLACEMENT_HINTS = ("替换", "替代", "代替", "取代", "换成", "换掉")
    CONSTITUTION_HINTS = ("体质", "平和质", "气虚质", "阳虚质", "阴虚质", "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质")
    PRODUCT_HINTS = ("成药", "产品", "商品", "消费者", "消费", "口感", "好评", "复购", "送礼", "老人", "宝妈", "价格", "剂型")

    def classify(self, question: str) -> str:
        if any(hint in question for hint in self.REPLACEMENT_HINTS):
            return "formula_replacement"
        if any(hint in question for hint in self.CONSTITUTION_HINTS):
            return "constitution_recommendation"
        if any(hint in question for hint in self.PRODUCT_HINTS) and any(token in question for token in ("推荐", "适合", "哪些", "哪个", "成药", "产品", "商品")):
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
