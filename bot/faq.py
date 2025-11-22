from difflib import SequenceMatcher
from typing import Dict, Optional


class FAQResponder:
    def __init__(self, knowledge_base: Optional[Dict[str, str]] = None, threshold: float = 0.6):
        self.knowledge_base = knowledge_base or {}
        self.threshold = threshold

    def find_answer(self, question: str) -> Optional[str]:
        question = question.lower()
        best_match = None
        best_score = 0.0
        for q, answer in self.knowledge_base.items():
            score = SequenceMatcher(a=question, b=q.lower()).ratio()
            if score > self.threshold and score > best_score:
                best_score = score
                best_match = answer
        return best_match

