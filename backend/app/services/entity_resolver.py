import re

from app.repositories.neo4j_repository import Neo4jRepository


class EntityResolver:
    def __init__(self, neo4j_repository: Neo4jRepository) -> None:
        self.neo4j_repository = neo4j_repository
        self._noise_phrases = {
            "什么",
            "哪些",
            "哪个",
            "如何",
            "最好",
            "请问",
            "一下",
            "一下子",
            "介绍",
            "使用",
            "推荐",
            "适合",
            "有关",
            "相关",
            "相关的",
            "药食同源",
            "药材",
            "食材",
            "食疗",
            "作用",
            "功效",
            "成分",
            "症状",
            "疾病",
            "病症",
            "方剂",
            "方子",
            "方案",
            "原因",
            "以及",
            "还有",
            "可以",
            "需要",
            "怎么",
            "是不是",
            "是什么",
            "有哪些",
            "用什么",
            "什么症状",
            "什么方剂",
            "方剂最好",
            "化合物",
            "性味",
            "归经",
            "禁忌",
            "风味",
            "成药",
            "产品",
            "商品",
            "消费者",
            "画像",
            "口感",
            "价格",
            "剂型",
        }

    def resolve(self, question: str, preferred_types: list[str] | None = None) -> list[dict]:
        candidates = self._build_candidates(question)
        if not candidates:
            candidates = [question.strip()]
        return self.resolve_terms(candidates, preferred_types=preferred_types)

    def resolve_terms(self, terms: list[str], preferred_types: list[str] | None = None) -> list[dict]:
        candidates = [term.strip() for term in terms if term and term.strip()]
        if not candidates:
            return []

        results: list[dict] = []
        seen: set[str] = set()
        type_rank = {entity_type: index for index, entity_type in enumerate(preferred_types or [])}

        for candidate in candidates[:20]:
            min_score = self._min_score(candidate)
            if min_score > 140:
                continue
            for entity in self.neo4j_repository.search_entities(candidate, limit=10):
                if entity["id"] in seen:
                    continue
                if entity.get("score", 0) < min_score:
                    continue
                entity["_candidate"] = candidate
                entity["_type_rank"] = type_rank.get(entity.get("entity_type", ""), 99)
                results.append(entity)
                seen.add(entity["id"])

        results.sort(
            key=lambda item: (
                item.get("_type_rank", 99),
                -item.get("score", 0),
                -len(item.get("_candidate", "")),
                len(item.get("name", "")),
            )
        )
        for item in results:
            item.pop("_candidate", None)
            item.pop("_type_rank", None)
        return results[:12]

    def _build_candidates(self, question: str) -> list[str]:
        cleaned = re.sub(r"[？?，,。；;：:、（）()\[\]【】/\\\n\r\t]+", " ", question)
        segments = [segment.strip() for segment in cleaned.split() if segment.strip()]
        candidates: list[str] = []

        self._append_candidate(candidates, question.strip())
        for segment in segments:
            self._append_candidate(candidates, segment)

        for segment in segments:
            normalized = self._strip_noise_words(segment)
            self._append_candidate(candidates, normalized)
            for piece in self._extract_ngrams(normalized):
                self._append_candidate(candidates, piece)

        return candidates

    def _append_candidate(self, bucket: list[str], candidate: str) -> None:
        candidate = candidate.strip()
        if not candidate:
            return
        if self._is_noise_candidate(candidate):
            return
        if candidate not in bucket:
            bucket.append(candidate)

    def _extract_ngrams(self, text: str) -> list[str]:
        compact = re.sub(r"\s+", "", text)
        if not self._contains_cjk(compact):
            return []

        output: list[str] = []
        upper = min(6, len(compact))
        for size in range(upper, 1, -1):
            for index in range(0, len(compact) - size + 1):
                piece = compact[index : index + size]
                if self._is_noise_candidate(piece):
                    continue
                if piece not in output:
                    output.append(piece)
        return output

    def _strip_noise_words(self, text: str) -> str:
        cleaned = text
        for word in sorted(self._noise_phrases, key=len, reverse=True):
            cleaned = cleaned.replace(word, " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _is_noise_candidate(self, candidate: str) -> bool:
        compact = re.sub(r"\s+", "", candidate)
        if not compact:
            return True
        if compact in self._noise_phrases:
            return True
        if len(compact) == 1 and self._contains_cjk(compact):
            return True
        if all(char in "是什么如何哪些最好请问可否需要一下推荐使用以及有关相关的了呢吗吧" for char in compact):
            return True
        return False

    def _min_score(self, candidate: str) -> int:
        compact = re.sub(r"\s+", "", candidate)
        if not compact:
            return 999
        if self._contains_cjk(compact):
            if len(compact) <= 2:
                return 120
            if len(compact) <= 4:
                return 90
            return 80
        if compact.isascii() and len(compact) <= 3:
            return 110
        return 70

    def _contains_cjk(self, text: str) -> bool:
        return any("一" <= char <= "鿿" for char in text)
