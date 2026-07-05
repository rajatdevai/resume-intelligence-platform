import pytest
from pydantic import ValidationError
from app.models.schema import (
    ExperienceItem,
    ProjectItem,
    EducationItem,
    ResumeDocument,
    JDIntelligence,
    MatchResult,
    RecommendationPlan,
    RewriteResult,
    ValidationReport,
    ConfidenceScore
)

# ----------------- Happy Path Unit Tests -----------------

def test_experience_item_valid():
    item = ExperienceItem(
        company=" Google ",  # Testing whitespace stripping
        title="Software Engineer",
        start_date="2022-01",
        end_date="Present",
        bullets=["Wrote clean code.", "Optimized databases."]
    )
    assert item.company == "Google"  # Should be stripped
    assert item.title == "Software Engineer"
    assert item.start_date == "2022-01"
    assert item.end_date == "Present"
    assert len(item.bullets) == 2

def test_project_item_valid():
    item = ProjectItem(
        name="Resume Customizer",
        description="A full-stack agent platform",
        tech_stack=["FastAPI", "Next.js"],
        bullets=["Deployed to cloud."]
    )
    assert item.name == "Resume Customizer"
    assert item.description == "A full-stack agent platform"
    assert item.tech_stack == ["FastAPI", "Next.js"]

def test_education_item_valid():
    item = EducationItem(
        institution="MIT",
        degree="B.S. Computer Science",
        start_date="2018",
        end_date="2022"
    )
    assert item.institution == "MIT"
    assert item.degree == "B.S. Computer Science"

def test_resume_document_valid():
    resume = ResumeDocument(
        summary="Experienced dev",
        skills=["Python", "React"],
        experience=[
            ExperienceItem(company="A", title="Dev", start_date="2020", bullets=[])
        ],
        projects=[],
        education=[],
        certifications=["AWS Architect"],
        raw_text="Experienced dev. Python, React.",
        parse_warnings=[]
    )
    assert resume.summary == "Experienced dev"
    assert len(resume.experience) == 1
    assert resume.certifications == ["AWS Architect"]

def test_jd_intelligence_valid():
    jd = JDIntelligence(
        job_title=" Senior Backend Engineer ",
        must_have_skills=["Python", "FastAPI"],
        good_to_have_skills=["Kubernetes"],
        soft_skills=["Mentorship"],
        keywords=["REST", "Asyncio"],
        seniority_level="Senior",
        conflicts_detected=[]
    )
    assert jd.job_title == "Senior Backend Engineer"
    assert jd.seniority_level == "Senior"

def test_match_result_valid():
    match = MatchResult(
        matched_skills=["Python"],
        missing_skills=["FastAPI"],
        matched_projects=["Project X"],
        weak_sections=["summary"],
        keyword_coverage_pct=50.0
    )
    assert match.keyword_coverage_pct == 50.0

def test_recommendation_plan_valid():
    plan = RecommendationPlan(
        rewrite_summary=True,
        rewrite_experience_indices=[0],
        reorder_projects=False,
        skills_to_highlight=["Python"],
        missing_keywords=["FastAPI"],
        reasoning="Resume lacks backend framework keywords."
    )
    assert plan.rewrite_summary is True
    assert plan.reasoning == "Resume lacks backend framework keywords."

def test_rewrite_result_valid():
    resume = ResumeDocument(summary="New Summary")
    rewrite = RewriteResult(
        updated_resume=resume,
        sections_touched=["summary"],
        raw_llm_output="LLM Response Text"
    )
    assert rewrite.updated_resume.summary == "New Summary"
    assert rewrite.raw_llm_output == "LLM Response Text"

def test_validation_report_valid():
    report = ValidationReport(
        passed=True,
        violations=[],
        diff_summary={"summary": "Changed text"}
    )
    assert report.passed is True

def test_confidence_score_valid():
    score = ConfidenceScore(
        overall_confidence=95.0,
        jd_match_score=90.0,
        rewrite_quality_score=92.0,
        validation_score=100.0,
        ats_improvement_score=85.0,
        needs_human_review=False,
        explanation="Everything checks out perfectly."
    )
    assert score.overall_confidence == 95.0
    assert score.needs_human_review is False

# ----------------- Sad Path / Validation Errors -----------------

def test_experience_item_invalid_empty():
    with pytest.raises(ValidationError):
        ExperienceItem(company=" ", title="Engineer", start_date="2020")

def test_jd_intelligence_invalid_empty_title():
    with pytest.raises(ValidationError):
        JDIntelligence(job_title=" ", must_have_skills=[])

def test_match_result_invalid_coverage_bounds():
    # Test coverage too high
    with pytest.raises(ValidationError):
        MatchResult(
            matched_skills=[],
            missing_skills=[],
            matched_projects=[],
            weak_sections=[],
            keyword_coverage_pct=150.0
        )
    
    # Test coverage negative
    with pytest.raises(ValidationError):
        MatchResult(
            matched_skills=[],
            missing_skills=[],
            matched_projects=[],
            weak_sections=[],
            keyword_coverage_pct=-10.0
        )

def test_confidence_score_invalid_bounds():
    with pytest.raises(ValidationError):
        ConfidenceScore(
            overall_confidence=120.0,  # Invalid
            jd_match_score=90.0,
            rewrite_quality_score=92.0,
            validation_score=100.0,
            ats_improvement_score=85.0,
            needs_human_review=False,
            explanation="Explanation"
        )
    
    with pytest.raises(ValidationError):
        ConfidenceScore(
            overall_confidence=95.0,
            jd_match_score=-5.0,  # Invalid
            rewrite_quality_score=92.0,
            validation_score=100.0,
            ats_improvement_score=85.0,
            needs_human_review=False,
            explanation="Explanation"
        )
