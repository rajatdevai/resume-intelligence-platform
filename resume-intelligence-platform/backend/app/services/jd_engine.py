import re
from typing import List, Optional, Set
from app.models.schema import JDIntelligence
from app.utils.tech_keywords import TECH_KEYWORDS
from app.utils.soft_skills import SOFT_SKILLS

NICE_TO_HAVE_PATTERNS = [
    "nice to have", "nice-to-have", "preferred", "bonus", "plus", "optional", 
    "desired", "beneficial", "advantage", "good to have", "not required"
]

MUST_HAVE_PATTERNS = [
    "must", "required", "essential", "mandatory", "minimum", "need", "have to", 
    "expected", "qualification", "requirements"
]

def chunk_if_needed(jd_text: str) -> str:
    """
    If the Job Description exceeds 6000 characters, parses and truncates it, 
    preserving the introductory paragraph and paragraphs rich in keywords or requirements headings.
    """
    if len(jd_text) <= 6000:
        return jd_text

    paragraphs = [p.strip() for p in jd_text.split('\n\n') if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in jd_text.split('\n') if p.strip()]

    if not paragraphs:
        return jd_text[:6000]

    # Handle extremely large intro paragraphs
    intro_p = paragraphs[0]
    if len(intro_p) > 2000:
        intro_p = intro_p[:1500] + "\n[... truncated intro ...]"

    selected_paragraphs = [intro_p]
    headers_keywords = ["require", "responsib", "qualif", "role", "skill", "expect", "tech"]

    for p in paragraphs[1:]:
        p_lower = p.lower()
        has_header = any(h in p_lower for h in headers_keywords)
        
        kw_count = 0
        for kw in TECH_KEYWORDS:
            if re.search(rf'\b{re.escape(kw.lower())}\b', p_lower):
                kw_count += 1
                if kw_count >= 2:
                    break
                    
        if has_header or kw_count >= 2:
            selected_paragraphs.append(p)

    truncated_text = "\n\n".join(selected_paragraphs)
    if len(truncated_text) > 6000:
        return truncated_text[:6000]
        
    return truncated_text

def analyze_jd(jd_text: str) -> JDIntelligence:
    """
    Analyzes Job Description text to extract structured intelligence: job title, 
    mandatory skills, preferred skills, soft skills, seniority, and conflicts.
    """
    job_title = _extract_job_title(jd_text)
    must_have, good_to_have = _extract_technical_skills(jd_text)
    soft_skills = _extract_soft_skills(jd_text)
    seniority = _detect_seniority(jd_text)
    conflicts = _detect_conflicts(must_have, jd_text)

    # Keywords list is the union of technical skills and soft skills
    keywords = list(set(must_have + good_to_have + soft_skills))

    return JDIntelligence(
        job_title=job_title,
        must_have_skills=must_have,
        good_to_have_skills=good_to_have,
        soft_skills=soft_skills,
        keywords=keywords,
        seniority_level=seniority,
        conflicts_detected=conflicts
    )

def _extract_job_title(jd_text: str) -> str:
    lines = [l.strip() for l in jd_text.split('\n') if l.strip()]
    if not lines:
        return "Software Engineer"

    title = "Software Engineer"
    # Search first 3 lines for standard indicators
    for line in lines[:3]:
        match = re.search(r'\b(?:Role|Title|Position|Job Title)\s*:\s*(.+)$', line, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            break
            
        match_hiring = re.search(r'\b(?:hiring for|looking for a|looking for an)\s+(.+)$', line, re.IGNORECASE)
        if match_hiring:
            title = match_hiring.group(1).strip()
            break
    else:
        for line in lines[:3]:
            if len(line) < 80 and not line.startswith(('-', '*', '•')):
                title = line
                break
            
    # Clean prefixes from title
    title = re.sub(r'^(?:Hiring\s*for\s*:?|Hiring\s*:?|Looking\s*for\s*:?|Role\s*:?|Title\s*:?|Position\s*:?)\s*', '', title, flags=re.IGNORECASE)
    return title.strip()

def _extract_technical_skills(jd_text: str) -> tuple[List[str], List[str]]:
    # Split text into sentences for local proximity evaluation
    # Split on periods followed by spaces, or newlines
    sentences = re.split(r'(?<=[.!?])\s+|\n+', jd_text)
    
    must_have: Set[str] = set()
    good_to_have: Set[str] = set()
    
    # Track section headers to inherit context
    in_preferred_section = False
    
    for sentence in sentences:
        sent_clean = sentence.strip()
        if not sent_clean:
            continue
            
        sent_lower = sent_clean.lower()
        
        # Check if line looks like a section header
        if len(sent_clean) < 50:
            if any(p in sent_lower for p in ["preferred", "nice to have", "plus", "bonus", "desirable", "optional"]):
                in_preferred_section = True
            elif any(p in sent_lower for p in ["required", "must have", "requirements", "qualification", "essential"]):
                in_preferred_section = False

        # Scan for tech keywords in the sentence
        for kw in TECH_KEYWORDS:
            escaped_kw = re.escape(kw.lower())
            
            # Use identical boundary checks as parser
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
                
            if re.search(pattern, sent_lower):
                # Proximity analysis
                is_preferred = in_preferred_section
                if not is_preferred:
                    # Check local context in the sentence
                    if any(p in sent_lower for p in NICE_TO_HAVE_PATTERNS):
                        is_preferred = True
                
                if is_preferred:
                    good_to_have.add(kw)
                else:
                    must_have.add(kw)
                    
    # Clean overlaps (if a skill is matched in both, default to must_have)
    good_to_have = good_to_have - must_have
    
    return list(must_have), list(good_to_have)

def _extract_soft_skills(jd_text: str) -> List[str]:
    extracted = []
    text_lower = jd_text.lower()
    for skill in SOFT_SKILLS:
        pattern = rf'\b{re.escape(skill.lower())}\b'
        if re.search(pattern, text_lower):
            extracted.append(skill)
    return extracted

def _detect_seniority(jd_text: str) -> Optional[str]:
    text_lower = jd_text.lower()
    if any(k in text_lower for k in ["principal", "staff engineer", "lead developer", "lead engineer"]):
        return "Lead / Principal"
    if "senior" in text_lower:
        return "Senior"
    if any(k in text_lower for k in ["junior", "entry level", "entry-level", "intern"]):
        return "Junior"
    if any(k in text_lower for k in ["mid level", "mid-level", "intermediate"]):
        return "Mid"
    return None

def _detect_conflicts(must_have: List[str], jd_text: str) -> List[str]:
    conflicts = []
    must_have_lower = [s.lower() for s in must_have]
    
    # 1. Frontend conflicts (e.g. React vs Angular vs Vue vs Svelte)
    fe_frameworks = ["react", "angular", "vue", "svelte"]
    matched_fe = [fw for fw in fe_frameworks if fw in must_have_lower]
    
    if len(matched_fe) >= 2:
        for i in range(len(matched_fe)):
            for j in range(i + 1, len(matched_fe)):
                fw1, fw2 = matched_fe[i], matched_fe[j]
                # Check for "or", "/" in context of these two frameworks in the original text
                pattern = rf'{fw1}\s+(?:or|/|and/or)\s+{fw2}|{fw2}\s+(?:or|/|and/or)\s+{fw1}'
                if not re.search(pattern, jd_text, re.IGNORECASE):
                    fw1_cap = [s for s in must_have if s.lower() == fw1][0]
                    fw2_cap = [s for s in must_have if s.lower() == fw2][0]
                    conflicts.append(f"Multiple frontend frameworks required: {fw1_cap} and {fw2_cap} with no 'or' connector.")
                    
    # 2. Backend conflicts (e.g. Python, Java, C#, Ruby, Go, Rust)
    be_languages = ["python", "java", "c#", "ruby", "go", "rust"]
    matched_be = [lang for lang in be_languages if lang in must_have_lower]
    
    if len(matched_be) >= 2:
        for i in range(len(matched_be)):
            for j in range(i + 1, len(matched_be)):
                l1, l2 = matched_be[i], matched_be[j]
                pattern = rf'{l1}\s+(?:or|/|and/or)\s+{l2}|{l2}\s+(?:or|/|and/or)\s+{l1}'
                if not re.search(pattern, jd_text, re.IGNORECASE):
                    l1_cap = [s for s in must_have if s.lower() == l1][0]
                    l2_cap = [s for s in must_have if s.lower() == l2][0]
                    conflicts.append(f"Multiple backend languages required: {l1_cap} and {l2_cap} with no 'or' connector.")
                    
    return conflicts
