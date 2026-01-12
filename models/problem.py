from dataclasses import dataclass
from typing import List


@dataclass
class Problem:
    discard: bool
    problem_summary: str
    who_has_it: str
    why_it_matters: str
    current_bad_solutions: List[str]
    urgency_score: int
    evidence_quotes: List[str]

    def to_dict(self):
        return {
            "discard": self.discard,
            "problem_summary": self.problem_summary,
            "who_has_it": self.who_has_it,
            "why_it_matters": self.why_it_matters,
            "current_bad_solutions": self.current_bad_solutions,
            "urgency_score": self.urgency_score,
            "evidence_quotes": self.evidence_quotes
        }
