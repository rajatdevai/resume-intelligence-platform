import pytest
from app.models.schema import (
    ResumeDocument, ExperienceItem, ProjectItem, EducationItem, RecommendationPlan
)
from app.services.validator import validate

# Helper base fixtures

def get_base_original():
    return ResumeDocument(
        summary="Experienced SWE with Python and Docker skills.",
        skills=["Python", "Docker"],
        inferred_skills=["FastAPI"],
        experience=[
            ExperienceItem(
                company="Google",
                title="SWE",
                start_date="2020-01",
                end_date="Present",
                bullets=["Built backends using Python."]
            ),
            ExperienceItem(
                company="Meta",
                title="SWE",
                start_date="2018-01",
                end_date="2020-01",
                bullets=["Worked on frontend systems."]
            )
        ],
        projects=[
            ProjectItem(name="My App", description="API", tech_stack=["Python"], bullets=[])
        ],
        education=[
            EducationItem(
                institution="MIT",
                degree="B.S. CS",
                start_date="2014-09",
                end_date="2018-05"
            )
        ],
        certifications=["AWS Architect"],
        raw_text="Google Meta Python Docker FastAPI SWE MIT B.S. CS 2020 2018 2014 AWS",
        parse_warnings=[]
    )

def get_base_plan():
    return RecommendationPlan(
        rewrite_summary=True,
        rewrite_experience_indices=[0],
        reorder_projects=False,
        skills_to_highlight=["Python", "FastAPI"],
        missing_keywords=[],
        reasoning="Plan reasoning"
    )

# ----------------- Check 1: Company mismatch -----------------
def test_validation_company_mismatch():
    orig = get_base_original()
    rewr = orig.model_copy(deep=True)
    rewr.experience[0].company = "Micro-soft"  # Factual error / fabrication
    
    plan = get_base_plan()
    report = validate(orig, rewr, plan)
    
    assert report.passed is False
    assert any("company name mismatch" in v.lower() for v in report.violations)

# ----------------- Check 2: Dates unchanged -----------------
def test_validation_date_change():
    orig = get_base_original()
    
    # 1. Experience date edit
    rewr_exp = orig.model_copy(deep=True)
    rewr_exp.experience[0].start_date = "2020-02"
    plan = get_base_plan()
    report1 = validate(orig, rewr_exp, plan)
    assert report1.passed is False
    assert any("start date changed" in v.lower() for v in report1.violations)
    
    # 2. Education date edit
    rewr_edu = orig.model_copy(deep=True)
    rewr_edu.education[0].end_date = "2018-06"
    report2 = validate(orig, rewr_edu, plan)
    assert report2.passed is False
    assert any("education end date changed" in v.lower() for v in report2.violations)

# ----------------- Check 3: Education institution/degree unchanged -----------------
def test_validation_education_details_change():
    orig = get_base_original()
    rewr = orig.model_copy(deep=True)
    rewr.education[0].institution = "Stanford"
    
    plan = get_base_plan()
    report = validate(orig, rewr, plan)
    assert report.passed is False
    assert any("institution changed" in v.lower() for v in report.violations)

# ----------------- Check 4: Fabricated skills -----------------
def test_validation_fabricated_skills():
    orig = get_base_original()
    
    # 1. Plan invariant check: trying to highlight a skill the candidate doesn't have (Kubernetes)
    plan_invalid = RecommendationPlan(
        rewrite_summary=True,
        rewrite_experience_indices=[],
        skills_to_highlight=["Kubernetes"],  # Fabricated target
        reasoning="Highlight Kubernetes"
    )
    report1 = validate(orig, orig, plan_invalid)
    assert report1.passed is False
    assert any("invariant violation" in v.lower() for v in report1.violations)
    
    # 2. Skill list check: rewriter sneaking a skill into rewr.skills list
    rewr = orig.model_copy(deep=True)
    rewr.skills.append("Kubernetes")  # Fabricated skill
    plan = get_base_plan()
    report2 = validate(orig, rewr, plan)
    assert report2.passed is False
    assert any("skill list fabrication" in v.lower() for v in report2.violations)

# ----------------- Check 5: Untouched sections altered -----------------
def test_validation_untouched_section_altered():
    orig = get_base_original()
    
    # Plan says experience index 1 is untouched, but rewriter edited it
    rewr = orig.model_copy(deep=True)
    rewr.experience[1].bullets = ["Rewritten bullet without indexing plan permission"]
    
    plan = get_base_plan()  # plan only allows index 0
    report = validate(orig, rewr, plan)
    assert report.passed is False
    assert any("modified but index was not in" in v.lower() for v in report.violations)

# ----------------- Check 6: Tech term hallucination in bullets -----------------
def test_validation_tech_term_hallucination():
    orig = get_base_original()
    
    # Rewriter sneaks "Kafka" into index 0's bullets, which is NOT in original raw text
    rewr = orig.model_copy(deep=True)
    rewr.experience[0].bullets = ["Wrote Python scripts and implemented Kafka message streams."]
    
    plan = get_base_plan()
    report = validate(orig, rewr, plan)
    
    assert report.passed is False
    assert any("fabricated technology 'kafka'" in v.lower() for v in report.violations)

# ----------------- Happy Path Validation -----------------
def test_validation_happy_path_success():
    orig = get_base_original()
    rewr = orig.model_copy(deep=True)
    rewr.summary = "Experienced Python Software Engineer with Docker expertise."
    rewr.experience[0].bullets = ["Optimized backends using Python."]
    
    plan = get_base_plan()
    report = validate(orig, rewr, plan)
    
    assert report.passed is True
    assert len(report.violations) == 0
    assert "summary" in report.diff_summary
    assert "experience_0" in report.diff_summary
