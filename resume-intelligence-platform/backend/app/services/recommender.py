import re
from app.models.schema import ResumeDocument, JDIntelligence, MatchResult, RecommendationPlan

def recommend(resume: ResumeDocument, jd: JDIntelligence, match_res: MatchResult) -> RecommendationPlan:
    """
    Builds a list of action items / instructions to align the candidate resume 
    to the job requirements. Outputs instructions, never fabricated resume text.
    """
    # 1. Summary rewrite trigger
    rewrite_summary = "summary" in match_res.weak_sections or match_res.keyword_coverage_pct < 70.0

    # 2. Experience indices to rewrite
    # Targets experience roles where bullets lack matched skills but the candidate possesses must_have skills elsewhere
    rewrite_experience_indices = []
    candidate_must_haves_lower = {s.lower() for s in (resume.skills + resume.inferred_skills)}.intersection(
        {s.lower() for s in jd.must_have_skills}
    )
    
    for idx, exp in enumerate(resume.experience):
        bullets_text = " ".join(exp.bullets).lower()
        has_matched_skill = any(re.search(rf'\b{re.escape(ms.lower())}\b', bullets_text) for ms in match_res.matched_skills)
        
        if not has_matched_skill:
            # Check if candidate has salvageable must-have skills they can mention in this role
            if candidate_must_haves_lower:
                rewrite_experience_indices.append(idx)

    # 3. Project reordering checks
    # True if a project later in the list has more overlap with must_have skills than the first project
    reorder_projects = False
    if len(resume.projects) > 1:
        must_have_lower = {s.lower() for s in jd.must_have_skills}
        first_proj_tech = {t.lower() for t in resume.projects[0].tech_stack}
        first_proj_overlap = len(first_proj_tech.intersection(must_have_lower))
        
        for proj in resume.projects[1:]:
            proj_tech = {t.lower() for t in proj.tech_stack}
            proj_overlap = len(proj_tech.intersection(must_have_lower))
            if proj_overlap > first_proj_overlap:
                reorder_projects = True
                break

    # 4. Highlight matched must-haves
    skills_to_highlight = [
        s for s in jd.must_have_skills 
        if s.lower() in {ms.lower() for ms in match_res.matched_skills}
    ]

    # 5. Missing keywords
    missing_keywords = match_res.missing_skills

    # 6. Plain-English reasoning
    reasoning = (
        f"The plan targets alignment with the '{jd.job_title}' requirements. "
        f"Overall keyword coverage is calculated at {match_res.keyword_coverage_pct:.1f}%. "
        f"Key optimizations include: "
        f"{'rewriting the summary section to include target title and core must-have skills; ' if rewrite_summary else 'retaining the summary which shows sufficient alignment; '}"
        f"{f'focusing bullet points for roles at indices {rewrite_experience_indices} to showcase skills like {list(candidate_must_haves_lower)[:3]}; ' if rewrite_experience_indices else ''}"
        f"{'reordering projects to lead with the most stack-aligned work; ' if reorder_projects else 'maintaining project hierarchy; '}"
        f"and emphasizing matched strengths: {skills_to_highlight[:4]}."
    )

    return RecommendationPlan(
        rewrite_summary=rewrite_summary,
        rewrite_experience_indices=rewrite_experience_indices,
        reorder_projects=reorder_projects,
        skills_to_highlight=skills_to_highlight,
        missing_keywords=missing_keywords,
        reasoning=reasoning
    )
