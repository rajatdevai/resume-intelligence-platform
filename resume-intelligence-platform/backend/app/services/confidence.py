import re
import difflib
from typing import Optional
from app.models.schema import ResumeDocument, MatchResult, ValidationReport, RecommendationPlan, ConfidenceScore

def score(
    match: MatchResult,
    validation: ValidationReport,
    original: ResumeDocument,
    rewritten: ResumeDocument,
    plan: Optional[RecommendationPlan] = None
) -> ConfidenceScore:
    """
    Computes a composite confidence score (0 to 100) evaluating the quality and alignment 
    of the rewritten resume.
    """
    # 1. JD Match Score
    jd_match_score = match.keyword_coverage_pct

    # 2. Validation Score
    validation_score = 100.0 if validation.passed else 20.0

    # 3. Rewrite Quality Score
    # Evaluates word-diff changes outside expected touched areas
    # If plan is not passed, infer what was touched based on actual differences
    rewrite_summary_expected = plan.rewrite_summary if plan else (original.summary != rewritten.summary)
    rewrite_exp_indices_expected = plan.rewrite_experience_indices if plan else [
        i for i in range(len(original.experience))
        if i < len(rewritten.experience) and original.experience[i].bullets != rewritten.experience[i].bullets
    ]

    total_untouched_words = 0
    changed_untouched_words = 0

    # Summary
    if not rewrite_summary_expected:
        words_orig = original.summary.split()
        words_rewr = rewritten.summary.split()
        total_untouched_words += len(words_orig)
        diff = [d for d in difflib.ndiff(words_orig, words_rewr) if d.startswith('+') or d.startswith('-')]
        changed_untouched_words += len(diff)

    # Experience bullets
    for i in range(len(original.experience)):
        if i not in rewrite_exp_indices_expected:
            words_orig = " ".join(original.experience[i].bullets).split()
            words_rewr = " ".join(rewritten.experience[i].bullets).split() if i < len(rewritten.experience) else []
            total_untouched_words += len(words_orig)
            diff = [d for d in difflib.ndiff(words_orig, words_rewr) if d.startswith('+') or d.startswith('-')]
            changed_untouched_words += len(diff)

    # Projects (not planned for rewrites)
    words_orig_proj = " ".join([p.name + " " + p.description + " " + " ".join(p.tech_stack) for p in original.projects]).split()
    words_rewr_proj = " ".join([p.name + " " + p.description + " " + " ".join(p.tech_stack) for p in rewritten.projects]).split()
    total_untouched_words += len(words_orig_proj)
    diff_proj = [d for d in difflib.ndiff(words_orig_proj, words_rewr_proj) if d.startswith('+') or d.startswith('-')]
    changed_untouched_words += len(diff_proj)

    # Education (not planned for rewrites)
    words_orig_edu = " ".join([e.institution + " " + e.degree for e in original.education]).split()
    words_rewr_edu = " ".join([e.institution + " " + e.degree for e in rewritten.education]).split()
    total_untouched_words += len(words_orig_edu)
    diff_edu = [d for d in difflib.ndiff(words_orig_edu, words_rewr_edu) if d.startswith('+') or d.startswith('-')]
    changed_untouched_words += len(diff_edu)

    # Certifications (not planned for rewrites)
    words_orig_cert = " ".join(original.certifications).split()
    words_rewr_cert = " ".join(rewritten.certifications).split()
    total_untouched_words += len(words_orig_cert)
    diff_cert = [d for d in difflib.ndiff(words_orig_cert, words_rewr_cert) if d.startswith('+') or d.startswith('-')]
    changed_untouched_words += len(diff_cert)

    ratio = changed_untouched_words / total_untouched_words if total_untouched_words > 0 else 0.0
    rewrite_quality_score = max(0.0, min(1.0, 1.0 - ratio)) * 100.0

    # 4. ATS Improvement Score
    # Compare keyword density of summary and experience sections before and after
    jd_keywords = {s.lower() for s in (match.matched_skills + match.missing_skills)}
    total_keywords = len(jd_keywords)

    if total_keywords == 0:
        ats_improvement_score = 100.0
    else:
        orig_bullets = []
        for exp in original.experience:
            orig_bullets.extend(exp.bullets)
        orig_text = (original.summary + " " + " ".join(orig_bullets)).lower()

        rewr_bullets = []
        for exp in rewritten.experience:
            rewr_bullets.extend(exp.bullets)
        rewr_text = (rewritten.summary + " " + " ".join(rewr_bullets)).lower()

        orig_matches = 0
        rewr_matches = 0
        for kw in jd_keywords:
            pattern = rf'\b{re.escape(kw)}\b'
            if re.search(pattern, orig_text):
                orig_matches += 1
            if re.search(pattern, rewr_text):
                rewr_matches += 1

        orig_density = orig_matches / total_keywords
        rewr_density = rewr_matches / total_keywords

        if orig_density >= 1.0:
            ats_improvement_score = 100.0
        elif rewr_density >= orig_density:
            ats_improvement_score = ((rewr_density - orig_density) / (1.0 - orig_density)) * 100.0
        else:
            ats_improvement_score = 0.0

    # 5. Composite Score Calculation
    overall_confidence = (
        0.30 * jd_match_score +
        0.20 * rewrite_quality_score +
        0.30 * validation_score +
        0.20 * ats_improvement_score
    )
    overall_confidence = max(0.0, min(100.0, overall_confidence))

    # 6. Flag human review
    needs_human_review = overall_confidence < 75.0

    # 7. Explanation generation
    safety_check_str = "passed safety checks" if validation.passed else "failed safety checks"
    explanation = (
        f"Confidence is at {overall_confidence:.1f}% because "
        f"the resume matched {len(match.matched_skills)} of {total_keywords} required skills, "
        f"improved search optimization by {ats_improvement_score:.1f}%, "
        f"and the rewrite {safety_check_str}."
    )

    return ConfidenceScore(
        overall_confidence=overall_confidence,
        jd_match_score=jd_match_score,
        rewrite_quality_score=rewrite_quality_score,
        validation_score=validation_score,
        ats_improvement_score=ats_improvement_score,
        needs_human_review=needs_human_review,
        explanation=explanation
    )
