from dataclasses import dataclass
from typing import List


@dataclass
class Verdict:
    pass_: bool
    reasons: List[str]
    missing_elements: List[str]
    generic_language_detected: bool
    example_quality_score: int
    
    def to_dict(self):
        return {
            "pass": self.pass_,
            "reasons": self.reasons,
            "missing_elements": self.missing_elements,
            "generic_language_detected": self.generic_language_detected,
            "example_quality_score": self.example_quality_score
        }
