from dataclasses import dataclass
from typing import List


@dataclass
class ProductSpec:
    build: bool
    product_type: str
    working_title: str
    target_buyer: str
    job_to_be_done: str
    why_existing_products_fail: str
    deliverables: List[str]
    price_recommendation: float
    confidence: int
    
    def to_dict(self):
        return {
            "build": self.build,
            "product_type": self.product_type,
            "working_title": self.working_title,
            "target_buyer": self.target_buyer,
            "job_to_be_done": self.job_to_be_done,
            "why_existing_products_fail": self.why_existing_products_fail,
            "deliverables": self.deliverables,
            "price_recommendation": self.price_recommendation,
            "confidence": self.confidence
        }
