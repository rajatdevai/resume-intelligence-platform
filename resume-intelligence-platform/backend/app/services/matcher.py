import re
from typing import List, Set
from app.models.schema import ResumeDocument, JDIntelligence, MatchResult

def match(resume: ResumeDocument, jd: JDIntelligence) -> MatchResult:
    """
    Compares the parsed ResumeDocument against Job Description intelligence.
    Returns a MatchResult outlining matched skills, missing skills, weak sections, 
    and weighted keyword coverage percentage.
    """
    candidate_skills_lower = {s.lower() for s in (resume.skills + resume.inferred_skills)}
    must_have_lower = {s.lower() for s in jd.must_have_skills}
    good_to_have_lower = {s.lower() for s in jd.good_to_have_skills}
    
    jd_total_lower = must_have_lower.union(good_to_have_lower)
    
    # Matched & Missing skills
    matched_lower = candidate_skills_lower.intersection(jd_total_lower)
    missing_lower = jd_total_lower - candidate_skills_lower
    
    # Format with original casing
    all_jd_skills = jd.must_have_skills + jd.good_to_have_skills
    matched_skills = _preserve_casing(all_jd_skills, matched_lower)
    missing_skills = _preserve_casing(all_jd_skills, missing_lower)
    
    # Calculate weighted keyword coverage percentage
    # Must-have skills get 2x weight, good-to-have get 1x
    total_possible_weight = len(jd.must_have_skills) * 2.0 + len(jd.good_to_have_skills) * 1.0
    
    matched_must_have = candidate_skills_lower.intersection(must_have_lower)
    matched_good_to_have = candidate_skills_lower.intersection(good_to_have_lower)
    
    earned_weight = len(matched_must_have) * 2.0 + len(matched_good_to_have) * 1.0
    
    if total_possible_weight > 0:
        keyword_coverage_pct = (earned_weight / total_possible_weight) * 100.0
    else:
        keyword_coverage_pct = 100.0
        
    # Cap between 0 and 100
    keyword_coverage_pct = max(0.0, min(100.0, keyword_coverage_pct))
    
    # Matched Projects
    matched_projects = []
    for project in resume.projects:
        proj_tech_lower = {t.lower() for t in project.tech_stack}
        bullets_text = " ".join(project.bullets).lower()
        has_overlap = proj_tech_lower.intersection(jd_total_lower)
        has_keyword_in_bullets = any(re.search(rf'\b{re.escape(s)}\b', bullets_text) for s in jd_total_lower)
        
        if has_overlap or has_keyword_in_bullets:
            matched_projects.append(project.name)
            
    # Weak Sections
    weak_sections = []
    
    # 1. Summary Check
    summary_lower = resume.summary.lower()
    job_title_lower = jd.job_title.lower()
    has_title = job_title_lower in summary_lower or any(re.search(rf'\b{re.escape(w)}\b', summary_lower) for w in job_title_lower.split())
    has_must_have = any(re.search(rf'\b{re.escape(s)}\b', summary_lower) for s in must_have_lower)
    
    if not (has_title or has_must_have):
        weak_sections.append("summary")
        
    # 2. Experience Check
    all_exp_bullets = []
    for exp in resume.experience:
        all_exp_bullets.extend(exp.bullets)
    all_exp_text = " ".join(all_exp_bullets).lower()
    
    has_matched_in_exp = any(re.search(rf'\b{re.escape(ms)}\b', all_exp_text) for ms in matched_lower)
    if not has_matched_in_exp:
        weak_sections.append("experience")
        
    return MatchResult(
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        matched_projects=matched_projects,
        weak_sections=weak_sections,
        keyword_coverage_pct=keyword_coverage_pct
    )

def _preserve_casing(original_list: List[str], target_set_lower: Set[str]) -> List[str]:
    seen = set()
    result = []
    for item in original_list:
        item_lower = item.lower()
        if item_lower in target_set_lower and item_lower not in seen:
            seen.add(item_lower)
            result.append(item.strip())
    return result
