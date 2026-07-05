import pytest
from app.services.jd_engine import analyze_jd, chunk_if_needed

def test_nice_to_have_partitions_correctly():
    jd_text = """
    Hiring: Senior Backend Developer
    Requirements:
    - We require Python and FastAPI development experience.
    Nice to have:
    - Experience with AWS and Docker is a plus.
    - Having SQL experience is preferred.
    """
    
    intel = analyze_jd(jd_text)
    
    assert intel.job_title == "Senior Backend Developer"
    assert intel.seniority_level == "Senior"
    
    # Must have should contain Python and FastAPI
    assert "Python" in intel.must_have_skills
    assert "FastAPI" in intel.must_have_skills
    
    # Good to have should contain AWS, Docker, SQL
    assert "AWS" in intel.good_to_have_skills
    assert "Docker" in intel.good_to_have_skills
    assert "SQL" in intel.good_to_have_skills
    
    # Assert AWS is NOT in must_have
    assert "AWS" not in intel.must_have_skills

def test_mutually_exclusive_framework_conflict_triggered():
    jd_text = """
    Hiring for Front-end Developer position.
    
    Must-haves:
    - 5 years of React experience.
    - 3 years of Angular experience.
    
    Soft skills:
    - Mentorship and leadership are expected.
    """
    
    intel = analyze_jd(jd_text)
    
    assert "React" in intel.must_have_skills
    assert "Angular" in intel.must_have_skills
    assert "Mentorship" in intel.soft_skills
    
    # Conflicts detected because React and Angular are both required with no "or"
    assert len(intel.conflicts_detected) == 1
    assert "Multiple frontend frameworks required: React and Angular with no 'or' connector." in intel.conflicts_detected

def test_mutually_exclusive_with_or_no_conflict():
    jd_text = """
    Title: Senior Frontend Engineer
    
    We are looking for a developer with React or Angular experience.
    We also require Python.
    """
    
    intel = analyze_jd(jd_text)
    
    assert "React" in intel.must_have_skills
    assert "Angular" in intel.must_have_skills
    
    # No conflict because they are connected with "or"
    assert len(intel.conflicts_detected) == 0

def test_chunking_long_jd():
    # Construct a string over 6000 characters
    intro = "Hiring for Staff Engineer. "
    filler = "This is some filler company text that goes on and on. " * 150
    requirements = "\n\nRequirements:\n- Must know Python and Kubernetes.\n- Collaboration and communication are expected."
    
    full_jd = intro + filler + requirements
    assert len(full_jd) > 6000
    
    truncated = chunk_if_needed(full_jd)
    
    # Length should now be reduced and fits the constraints
    assert len(truncated) <= 6000
    
    # Verifies it kept the intro and requirements paragraph
    assert "Staff Engineer" in truncated
    assert "Python" in truncated
    assert "Kubernetes" in truncated
