import pytest
from app.models.schema import (
    ResumeDocument, ExperienceItem, ProjectItem, EducationItem, JDIntelligence
)
from app.services.matcher import match
from app.services.recommender import recommend

def test_strong_keyword_coverage_no_summary_rewrite():
    # Candidate summary contains the job title and a must-have skill
    resume = ResumeDocument(
        summary="Experienced Software Engineer working with Python.",
        skills=["Python", "FastAPI", "React", "Docker"],
        inferred_skills=[],
        experience=[
            ExperienceItem(
                company="Google",
                title="SWE",
                start_date="2020-01",
                end_date="Present",
                bullets=["Developed backends using Python and FastAPI."]
            )
        ],
        projects=[],
        education=[],
        certifications=[]
    )
    
    jd = JDIntelligence(
        job_title="Software Engineer",
        must_have_skills=["Python", "FastAPI"],
        good_to_have_skills=["React"],
        soft_skills=[],
        keywords=["Python", "FastAPI", "React"],
        seniority_level="Mid",
        conflicts_detected=[]
    )
    
    match_res = match(resume, jd)
    assert match_res.keyword_coverage_pct >= 70.0
    assert "summary" not in match_res.weak_sections
    
    plan = recommend(resume, jd, match_res)
    
    assert plan.rewrite_summary is False
    assert plan.reorder_projects is False
    assert len(plan.rewrite_experience_indices) == 0

def test_mismatched_top_project_triggers_reorder():
    resume = ResumeDocument(
        summary="Dev",
        skills=["Python", "FastAPI"],
        experience=[],
        projects=[
            ProjectItem(
                name="Front-end Static Site",
                description="HTML site",
                tech_stack=["HTML", "CSS"],
                bullets=[]
            ),
            ProjectItem(
                name="API Engine",
                description="FastAPI service",
                tech_stack=["Python", "FastAPI"],
                bullets=[]
            )
        ],
        education=[],
        certifications=[]
    )
    
    jd = JDIntelligence(
        job_title="Backend Developer",
        must_have_skills=["Python", "FastAPI"],
        good_to_have_skills=[],
        soft_skills=[],
        keywords=["Python", "FastAPI"],
        seniority_level="Mid",
        conflicts_detected=[]
    )
    
    match_res = match(resume, jd)
    plan = recommend(resume, jd, match_res)
    
    # Project 1 has more overlap (2) than Project 0 (0), so it should trigger reordering
    assert plan.reorder_projects is True

def test_experience_index_rewrite_trigger():
    resume = ResumeDocument(
        summary="Software Engineer Python",
        skills=["Python"],  # Python is known
        inferred_skills=[],
        experience=[
            ExperienceItem(
                company="Active Tech",
                title="SWE",
                start_date="2020-01",
                end_date="Present",
                bullets=["Developed Python scripts."]  # Mentions Python
            ),
            ExperienceItem(
                company="Silent Tech",
                title="SWE",
                start_date="2018-01",
                end_date="2020-01",
                bullets=["Managed server installations."]  # Zero matched skills, but candidate knows Python
            )
        ],
        projects=[],
        education=[],
        certifications=[]
    )
    
    jd = JDIntelligence(
        job_title="Software Engineer",
        must_have_skills=["Python"],
        good_to_have_skills=[],
        soft_skills=[],
        keywords=["Python"],
        seniority_level="Mid",
        conflicts_detected=[]
    )
    
    match_res = match(resume, jd)
    plan = recommend(resume, jd, match_res)
    
    # Experience at index 1 has no Python, but candidate knows Python elsewhere, so it is salvageable
    assert plan.rewrite_experience_indices == [1]
