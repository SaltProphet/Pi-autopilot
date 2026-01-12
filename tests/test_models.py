"""Tests for model classes."""
import pytest
from models.problem import Problem
from models.product_spec import ProductSpec
from models.verdict import Verdict


@pytest.mark.unit
class TestProblem:
    """Test suite for Problem model."""

    def test_problem_creation(self):
        """Test creating a Problem instance."""
        problem = Problem(
            discard=False,
            problem_summary="Test problem",
            who_has_it="Developers",
            why_it_matters="High impact",
            current_bad_solutions=["Solution A", "Solution B"],
            urgency_score=8,
            evidence_quotes=["Quote 1", "Quote 2"]
        )
        
        assert problem.discard is False
        assert problem.problem_summary == "Test problem"
        assert problem.urgency_score == 8
        assert len(problem.evidence_quotes) == 2

    def test_problem_to_dict(self):
        """Test converting Problem to dictionary."""
        problem = Problem(
            discard=True,
            problem_summary="Generic complaint",
            who_has_it="Everyone",
            why_it_matters="Not urgent",
            current_bad_solutions=[],
            urgency_score=2,
            evidence_quotes=[]
        )
        
        result = problem.to_dict()
        
        assert isinstance(result, dict)
        assert result["discard"] is True
        assert result["problem_summary"] == "Generic complaint"
        assert result["urgency_score"] == 2
        assert "who_has_it" in result
        assert "evidence_quotes" in result

    def test_problem_with_empty_lists(self):
        """Test Problem with empty lists."""
        problem = Problem(
            discard=False,
            problem_summary="Minimal problem",
            who_has_it="Users",
            why_it_matters="Important",
            current_bad_solutions=[],
            urgency_score=5,
            evidence_quotes=[]
        )
        
        assert problem.current_bad_solutions == []
        assert problem.evidence_quotes == []


@pytest.mark.unit
class TestProductSpec:
    """Test suite for ProductSpec model."""

    def test_product_spec_creation(self):
        """Test creating a ProductSpec instance."""
        spec = ProductSpec(
            build=True,
            product_type="Template",
            working_title="Test Template",
            target_buyer="Small business owners",
            job_to_be_done="Automate workflow",
            why_existing_products_fail="Too complex",
            deliverables=["Template file", "Guide", "Examples"],
            price_recommendation=29.99,
            confidence=85
        )
        
        assert spec.build is True
        assert spec.product_type == "Template"
        assert spec.confidence == 85
        assert len(spec.deliverables) == 3

    def test_product_spec_to_dict(self):
        """Test converting ProductSpec to dictionary."""
        spec = ProductSpec(
            build=False,
            product_type="Course",
            working_title="Test Course",
            target_buyer="Students",
            job_to_be_done="Learn skill",
            why_existing_products_fail="Outdated",
            deliverables=["Video", "Quiz"],
            price_recommendation=49.99,
            confidence=70
        )
        
        result = spec.to_dict()
        
        assert isinstance(result, dict)
        assert result["build"] is False
        assert result["product_type"] == "Course"
        assert result["price_recommendation"] == 49.99
        assert result["confidence"] == 70
        assert len(result["deliverables"]) == 2

    def test_product_spec_confidence_boundary(self):
        """Test ProductSpec with boundary confidence values."""
        spec_low = ProductSpec(
            build=False,
            product_type="Guide",
            working_title="Low Confidence",
            target_buyer="Anyone",
            job_to_be_done="Something",
            why_existing_products_fail="Unknown",
            deliverables=["Item"],
            price_recommendation=10.0,
            confidence=69
        )
        
        spec_high = ProductSpec(
            build=True,
            product_type="Template",
            working_title="High Confidence",
            target_buyer="Specific niche",
            job_to_be_done="Solve pain point",
            why_existing_products_fail="Clear gap",
            deliverables=["Item 1", "Item 2", "Item 3"],
            price_recommendation=39.99,
            confidence=95
        )
        
        assert spec_low.confidence == 69
        assert spec_high.confidence == 95

    def test_product_spec_minimum_deliverables(self):
        """Test ProductSpec with minimum deliverables count."""
        spec = ProductSpec(
            build=True,
            product_type="Package",
            working_title="Min Deliverables",
            target_buyer="Buyers",
            job_to_be_done="Task",
            why_existing_products_fail="Gap",
            deliverables=["One", "Two", "Three"],
            price_recommendation=25.0,
            confidence=80
        )
        
        assert len(spec.deliverables) >= 3


@pytest.mark.unit
class TestVerdict:
    """Test suite for Verdict model."""

    def test_verdict_creation(self):
        """Test creating a Verdict instance."""
        verdict = Verdict(
            pass_=True,
            reasons=["High quality", "Complete"],
            missing_elements=[],
            generic_language_detected=False,
            example_quality_score=9
        )
        
        assert verdict.pass_ is True
        assert len(verdict.reasons) == 2
        assert verdict.example_quality_score == 9

    def test_verdict_to_dict(self):
        """Test converting Verdict to dictionary."""
        verdict = Verdict(
            pass_=False,
            reasons=["Generic language", "Missing examples"],
            missing_elements=["Technical details", "Screenshots"],
            generic_language_detected=True,
            example_quality_score=4
        )
        
        result = verdict.to_dict()
        
        assert isinstance(result, dict)
        assert result["pass"] is False  # Note: pass_ becomes "pass" in dict
        assert len(result["reasons"]) == 2
        assert len(result["missing_elements"]) == 2
        assert result["generic_language_detected"] is True
        assert result["example_quality_score"] == 4

    def test_verdict_quality_threshold(self):
        """Test Verdict with quality score boundary."""
        verdict_pass = Verdict(
            pass_=True,
            reasons=["Excellent"],
            missing_elements=[],
            generic_language_detected=False,
            example_quality_score=7
        )
        
        verdict_fail = Verdict(
            pass_=False,
            reasons=["Low quality"],
            missing_elements=["Examples"],
            generic_language_detected=False,
            example_quality_score=6
        )
        
        assert verdict_pass.example_quality_score >= 7
        assert verdict_fail.example_quality_score < 7

    def test_verdict_empty_collections(self):
        """Test Verdict with empty reasons and missing_elements."""
        verdict = Verdict(
            pass_=True,
            reasons=[],
            missing_elements=[],
            generic_language_detected=False,
            example_quality_score=10
        )
        
        assert verdict.reasons == []
        assert verdict.missing_elements == []

    def test_verdict_fail_conditions(self):
        """Test various Verdict failure conditions."""
        # Fail due to generic language
        verdict1 = Verdict(
            pass_=False,
            reasons=["Generic language detected"],
            missing_elements=[],
            generic_language_detected=True,
            example_quality_score=8
        )
        
        # Fail due to missing elements
        verdict2 = Verdict(
            pass_=False,
            reasons=["Missing required sections"],
            missing_elements=["Introduction", "Conclusion"],
            generic_language_detected=False,
            example_quality_score=8
        )
        
        # Fail due to low quality score
        verdict3 = Verdict(
            pass_=False,
            reasons=["Poor examples"],
            missing_elements=[],
            generic_language_detected=False,
            example_quality_score=5
        )
        
        assert verdict1.generic_language_detected is True
        assert len(verdict2.missing_elements) > 0
        assert verdict3.example_quality_score < 7
