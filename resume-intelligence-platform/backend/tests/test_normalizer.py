import pytest
from app.models.schema import ResumeDocument, ExperienceItem
from app.services.parser import parse_resume
from app.services.normalizer import normalize
from tests.test_parser import create_valid_pdf

def test_career_objective_maps_to_summary():
    resume_text = """
Career Objective
Ambitious software engineer looking to optimize full stack platforms.

Work Experience
Google | Software Engineer | Jan 2020 - Present
- Built search tools
"""
    # Create valid PDF bytes
    file_bytes = create_valid_pdf(resume_text)
    
    # Parse resume
    doc = parse_resume(file_bytes, "resume.pdf")
    
    # Assert objective mapped to summary
    assert doc.summary is not None
    assert "ambitious software engineer" in doc.summary.lower()

def test_resume_inferred_skills():
    resume_text = """
Career Objective
Developer specializing in cloud deployments.

Work Experience
Amazon | Software Engineer | 2020 - 2022
- Wrote microservices in Python and deployed on AWS with Kubernetes.
- Managed relational databases using Postgres.
"""
    file_bytes = create_valid_pdf(resume_text)
    doc = parse_resume(file_bytes, "resume.pdf")
    
    # Explicit skills should be empty, but inferred_skills should list Python, AWS, Kubernetes, Postgres
    assert len(doc.skills) == 0
    assert "Python" in doc.inferred_skills
    assert "AWS" in doc.inferred_skills
    assert "Kubernetes" in doc.inferred_skills
    assert "Postgres" in doc.inferred_skills
    assert len(doc.inferred_skills) > 0
    
    # Parse warning should list the inference notice
    assert any("skills were inferred" in w for w in doc.parse_warnings)

def test_duplicate_skills_collapsing():
    doc = ResumeDocument(
        summary="Dev",
        skills=["React", "react", "REACT", "Python", "PYTHON", "FastAPI"],
        inferred_skills=["AWS", "aws"],
        experience=[],
        projects=[],
        education=[],
        certifications=[]
    )
    
    norm_doc = normalize(doc)
    
    # Skills should collapse to React, Python, FastAPI (preserving first occurrence casing)
    assert norm_doc.skills == ["React", "Python", "FastAPI"]
    assert norm_doc.inferred_skills == ["AWS"]

def test_date_normalization_success_and_warnings():
    doc = ResumeDocument(
        summary="Dev",
        skills=[],
        experience=[
            ExperienceItem(
                company="Google",
                title="SWE",
                start_date="Jan 2020",
                end_date="Present",
                bullets=[]
            ),
            ExperienceItem(
                company="Amazon",
                title="SWE",
                start_date="2018",
                end_date="05/2019",
                bullets=[]
            ),
            ExperienceItem(
                company="Meta",
                title="SWE",
                start_date="InvalidDateText",
                end_date="Ongoing",
                bullets=[]
            )
        ],
        projects=[],
        education=[],
        certifications=[]
    )
    
    norm_doc = normalize(doc)
    
    # Google item
    assert norm_doc.experience[0].start_date == "2020-01"
    assert norm_doc.experience[0].end_date == "Present"
    
    # Amazon item
    assert norm_doc.experience[1].start_date == "2018-01"
    assert norm_doc.experience[1].end_date == "2019-05"
    
    # Meta item
    assert norm_doc.experience[2].start_date == "InvalidDateText"  # Left as-is
    assert norm_doc.experience[2].end_date == "Present"  # Ongoing maps to Present
    
    # Meta start date warning should be present in parse_warnings
    assert any("Could not parse date format: 'InvalidDateText'" in w for w in norm_doc.parse_warnings)
