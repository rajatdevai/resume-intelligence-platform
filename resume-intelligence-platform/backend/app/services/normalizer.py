import re
from typing import List, Optional
from app.models.schema import ResumeDocument, ExperienceItem, EducationItem

MONTHS_MAP = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12"
}

def normalize(doc: ResumeDocument) -> ResumeDocument:
    """
    Normalizes a ResumeDocument by:
    1. Deduplicating explicit and inferred skills case-insensitively, preserving first occurrence casing.
    2. Trimming whitespace and filtering out empty bullet points in experience and projects.
    3. Formatting date fields to "YYYY-MM" or "Present" where possible, appending warnings for invalid structures.
    """
    # 1. Deduplicate explicit and inferred skills
    doc.skills = _normalize_skills(doc.skills)
    doc.inferred_skills = _normalize_skills(doc.inferred_skills)

    warnings = list(doc.parse_warnings)

    # 2. Normalize Experience items
    normalized_experience = []
    for item in doc.experience:
        # Clean bullets
        clean_bullets = [b.strip() for b in item.bullets if b.strip()]
        
        # Normalize dates
        start_norm, start_warn = _normalize_date(item.start_date)
        end_norm, end_warn = _normalize_date(item.end_date)
        
        if start_warn:
            warnings.append(f"Experience '{item.company}': {start_warn}")
        if end_warn:
            warnings.append(f"Experience '{item.company}': {end_warn}")
            
        normalized_experience.append(ExperienceItem(
            company=item.company.strip(),
            title=item.title.strip(),
            start_date=start_norm or item.start_date,
            end_date=end_norm or item.end_date,
            bullets=clean_bullets
        ))
    doc.experience = normalized_experience

    # 3. Normalize Project items
    for project in doc.projects:
        project.name = project.name.strip()
        project.description = project.description.strip()
        project.tech_stack = [t.strip() for t in project.tech_stack if t.strip()]
        project.bullets = [b.strip() for b in project.bullets if b.strip()]

    # 4. Normalize Education items
    normalized_education = []
    for item in doc.education:
        start_norm, start_warn = _normalize_date(item.start_date)
        end_norm, end_warn = _normalize_date(item.end_date)
        
        if start_warn:
            warnings.append(f"Education '{item.institution}': {start_warn}")
        if end_warn:
            warnings.append(f"Education '{item.institution}': {end_warn}")
            
        normalized_education.append(EducationItem(
            institution=item.institution.strip(),
            degree=item.degree.strip(),
            start_date=start_norm or item.start_date,
            end_date=end_norm or item.end_date
        ))
    doc.education = normalized_education

    # 5. Clean certifications & summary
    doc.certifications = [c.strip() for c in doc.certifications if c.strip()]
    doc.summary = doc.summary.strip()
    doc.parse_warnings = warnings

    return doc

def _normalize_skills(skills_list: List[str]) -> List[str]:
    seen = set()
    deduped = []
    for skill in skills_list:
        clean = skill.strip()
        if not clean:
            continue
        lower_val = clean.lower()
        if lower_val not in seen:
            seen.add(lower_val)
            deduped.append(clean)
    return deduped

def _normalize_date(date_str: Optional[str]) -> tuple[Optional[str], Optional[Optional[str]]]:
    if not date_str:
        return None, None
        
    date_clean = date_str.strip().lower()
    
    # Present checks
    if date_clean in ["present", "current", "ongoing", "now", "presently"]:
        return "Present", None
        
    # YYYY-MM
    match_ym = re.match(r'^(\d{4})-(\d{2})$', date_clean)
    if match_ym:
        return date_str.strip(), None
        
    # MM/YYYY
    match_my = re.match(r'^(\d{1,2})/(\d{4})$', date_clean)
    if match_my:
        month = match_my.group(1).zfill(2)
        year = match_my.group(2)
        return f"{year}-{month}", None
        
    # Mon YYYY / Month YYYY (e.g. Jan 2020, January 2020)
    match_mmy = re.match(r'^([a-z]{3,9})\s+(\d{4})$', date_clean)
    if match_mmy:
        month_str = match_mmy.group(1)
        year = match_mmy.group(2)
        if month_str in MONTHS_MAP:
            return f"{year}-{MONTHS_MAP[month_str]}", None
            
    # YYYY (normalize to YYYY-01)
    match_y = re.match(r'^(\d{4})$', date_clean)
    if match_y:
        return f"{date_clean}-01", None
        
    return date_str.strip(), f"Could not parse date format: '{date_str}'"
