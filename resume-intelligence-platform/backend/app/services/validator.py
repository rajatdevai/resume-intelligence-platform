import re
import difflib
from typing import List, Dict, Any
from app.models.schema import ResumeDocument, RecommendationPlan, ValidationReport
from app.utils.tech_keywords import TECH_KEYWORDS

def validate(original: ResumeDocument, rewritten: ResumeDocument, plan: RecommendationPlan) -> ValidationReport:
    """
    Validates the LLM-rewritten resume against the original resume for factual honesty.
    Checks:
    1. Company names are unchanged at each index.
    2. Dates (start/end) are unchanged for all work/edu items.
    3. Education details (institution/degree) are unchanged.
    4. No new fabricated skills in the rewritten skills list.
    5. Untouched sections remain byte/object-identical.
    6. Hallucination check: any technology term in rewritten bullets must exist in original.raw_text.
    """
    violations = []
    diff_summary = {}

    # Check length invariants
    if len(original.experience) != len(rewritten.experience):
        violations.append("Experience section length mismatch (roles added or deleted).")
        return ValidationReport(passed=False, violations=violations, diff_summary={})
        
    if len(original.education) != len(rewritten.education):
        violations.append("Education section length mismatch.")
        return ValidationReport(passed=False, violations=violations, diff_summary={})

    # Rule 1 & 2: Experience company names and dates validation
    for i in range(len(original.experience)):
        orig_exp = original.experience[i]
        rewr_exp = rewritten.experience[i]
        
        # Company name case-insensitive check
        if orig_exp.company.strip().lower() != rewr_exp.company.strip().lower():
            violations.append(f"Company name mismatch at experience index {i}: '{rewr_exp.company}' vs '{orig_exp.company}'.")
            
        # Date checks
        if orig_exp.start_date.strip() != rewr_exp.start_date.strip():
            violations.append(f"Start date changed at experience index {i}: '{rewr_exp.start_date}' vs '{orig_exp.start_date}'.")
        if (orig_exp.end_date or "").strip() != (rewr_exp.end_date or "").strip():
            violations.append(f"End date changed at experience index {i}: '{rewr_exp.end_date}' vs '{orig_exp.end_date}'.")

    # Rule 2 & 3: Education institution, degree, and dates validation
    for i in range(len(original.education)):
        orig_edu = original.education[i]
        rewr_edu = rewritten.education[i]
        
        if orig_edu.institution.strip().lower() != rewr_edu.institution.strip().lower():
            violations.append(f"Education institution changed at index {i}: '{rewr_edu.institution}' vs '{orig_edu.institution}'.")
        if orig_edu.degree.strip().lower() != rewr_edu.degree.strip().lower():
            violations.append(f"Education degree changed at index {i}: '{rewr_edu.degree}' vs '{orig_edu.degree}'.")
        if orig_edu.start_date.strip() != rewr_edu.start_date.strip():
            violations.append(f"Education start date changed at index {i}: '{rewr_edu.start_date}' vs '{orig_edu.start_date}'.")
        if (orig_edu.end_date or "").strip() != (rewr_edu.end_date or "").strip():
            violations.append(f"Education end date changed at index {i}: '{rewr_edu.end_date}' vs '{orig_edu.end_date}'.")

    # Rule 4: No new skills fabricated in rewritten skills list
    candidate_total_skills = {s.lower() for s in (original.skills + original.inferred_skills)}
    
    # Assert plan.skills_to_highlight invariant: they must exist in candidate's original skills
    for highlight in plan.skills_to_highlight:
        if highlight.lower() not in candidate_total_skills:
            violations.append(f"Plan invariant violation: target highlight skill '{highlight}' is not possessed by the candidate.")
            
    # Check rewritten.skills list holds only original or highlighted skills
    allowed_skills = {s.lower() for s in (original.skills + plan.skills_to_highlight)}
    for skill in rewritten.skills:
        if skill.lower() not in allowed_skills:
            violations.append(f"Skill list fabrication: rewritten resume contains new skill '{skill}' not present in original skills or highlight target.")

    # Rule 5: Untouched sections must be identical
    # Summary
    if not plan.rewrite_summary:
        if original.summary.strip() != rewritten.summary.strip():
            violations.append("Summary was rewritten but was not flagged in the optimization plan.")
    # Experience
    for i in range(len(original.experience)):
        if i not in plan.rewrite_experience_indices:
            # Bullet list check
            if original.experience[i].bullets != rewritten.experience[i].bullets:
                violations.append(f"Experience bullets at index {i} were modified but index was not in optimization plan.")
                
    # Projects
    if original.projects != rewritten.projects:
        violations.append("Projects list was modified but is not supported in the rewriter plan.")
    # Certifications
    if original.certifications != rewritten.certifications:
        violations.append("Certifications list was modified but is not supported in the rewriter plan.")

    # Rule 6: Hallucinated technology words in rewritten experience bullets
    orig_raw_lower = original.raw_text.lower()
    
    # Pre-compile a set of tech keywords found in original text
    tech_in_original = set()
    for kw in TECH_KEYWORDS:
        escaped_kw = re.escape(kw.lower())
        if kw.lower() == "c":
            pattern = rf'\bc\b(?!\+|#)'
        elif kw.lower() == "net":
            pattern = rf'(?<!\.)\bnet\b'
        elif kw.isalnum():
            pattern = rf'\b{escaped_kw}\b'
        else:
            prefix = r'\b' if kw[0].isalnum() else r'(?:^|[\s\.,;\!\?])'
            suffix = r'\b' if kw[-1].isalnum() else r'(?:$|[\s\.,;\!\?])'
            pattern = rf'{prefix}{escaped_kw}{suffix}'
            
        if re.search(pattern, orig_raw_lower):
            tech_in_original.add(kw.lower())

    # Scan rewritten bullets for new technologies
    for idx in plan.rewrite_experience_indices:
        if idx < len(rewritten.experience):
            exp_bullets = " ".join(rewritten.experience[idx].bullets).lower()
            for kw in TECH_KEYWORDS:
                escaped_kw = re.escape(kw.lower())
                if kw.lower() == "c":
                    pattern = rf'\bc\b(?!\+|#)'
                elif kw.lower() == "net":
                    pattern = rf'(?<!\.)\bnet\b'
                elif kw.isalnum():
                    pattern = rf'\b{escaped_kw}\b'
                else:
                    prefix = r'\b' if kw[0].isalnum() else r'(?:^|[\s\.,;\!\?])'
                    suffix = r'\b' if kw[-1].isalnum() else r'(?:$|[\s\.,;\!\?])'
                    pattern = rf'{prefix}{escaped_kw}{suffix}'
                    
                if re.search(pattern, exp_bullets):
                    if kw.lower() not in tech_in_original:
                        violations.append(f"Fabricated technology '{kw}' detected in rewritten bullets at experience index {idx}.")

    # Generate Word-Level Diff Summary for UI
    passed = len(violations) == 0
    if passed:
        # Summary diff
        if plan.rewrite_summary:
            words_orig = original.summary.split()
            words_rewr = rewritten.summary.split()
            diff_list = [line for line in difflib.ndiff(words_orig, words_rewr) if not line.startswith('?')]
            diff_summary["summary"] = diff_list
            
        # Experience diffs
        for idx in plan.rewrite_experience_indices:
            if idx < len(original.experience) and idx < len(rewritten.experience):
                bullets_orig = " ".join(original.experience[idx].bullets).split()
                bullets_rewr = " ".join(rewritten.experience[idx].bullets).split()
                diff_list = [line for line in difflib.ndiff(bullets_orig, bullets_rewr) if not line.startswith('?')]
                diff_summary[f"experience_{idx}"] = diff_list

    return ValidationReport(
        passed=passed,
        violations=violations,
        diff_summary=diff_summary
    )
