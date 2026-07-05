from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator

# Base config that applies string whitespace stripping
GLOBAL_CONFIG = ConfigDict(
    str_strip_whitespace=True,
    validate_assignment=True
)

class ExperienceItem(BaseModel):
    """
    Represents a single employment position or role in the candidate's experience.
    """
    model_config = GLOBAL_CONFIG

    company: str = Field(
        ...,
        min_length=1,
        description="The name of the employing company or organization."
    )
    title: str = Field(
        ...,
        min_length=1,
        description="The candidate's job title or role description."
    )
    start_date: str = Field(
        ...,
        min_length=1,
        description="Start date of employment (e.g. 'Jan 2020' or '2020-01')."
    )
    end_date: Optional[str] = Field(
        default=None,
        description="End date of employment, or 'Present' if current job."
    )
    bullets: List[str] = Field(
        default_factory=list,
        description="Bullet points describing accomplishments and responsibilities."
    )

class ProjectItem(BaseModel):
    """
    Represents an individual project completed by the candidate.
    """
    model_config = GLOBAL_CONFIG

    name: str = Field(
        ...,
        min_length=1,
        description="Name of the project."
    )
    description: str = Field(
        ...,
        min_length=1,
        description="High-level description of the project."
    )
    tech_stack: List[str] = Field(
        default_factory=list,
        description="Technologies, libraries, or tools used in the project."
    )
    bullets: List[str] = Field(
        default_factory=list,
        description="Detailed bullet points outlining achievements, scale, or metrics."
    )

class EducationItem(BaseModel):
    """
    Represents an educational qualification obtained by the candidate.
    """
    model_config = GLOBAL_CONFIG

    institution: str = Field(
        ...,
        min_length=1,
        description="Name of the university, college, or educational institution."
    )
    degree: str = Field(
        ...,
        min_length=1,
        description="Degree name, major, or specialization."
    )
    start_date: str = Field(
        ...,
        min_length=1,
        description="Start date of the academic period."
    )
    end_date: Optional[str] = Field(
        default=None,
        description="Graduation or end date, or 'Present' if ongoing."
    )

class ResumeDocument(BaseModel):
    """
    Standard schema for parsed, normalized, and customized resumes.
    """
    model_config = GLOBAL_CONFIG

    name: str = Field(
        default="",
        description="Candidate's full name extracted from the header."
    )
    contact_info: List[str] = Field(
        default_factory=list,
        description="Candidate's contact channels (email, phone, URLs) from the header."
    )
    summary: str = Field(
        default="",
        description="Professional summary or objective section."
    )
    skills: List[str] = Field(
        default_factory=list,
        description="List of technical and professional skills."
    )
    experience: List[ExperienceItem] = Field(
        default_factory=list,
        description="Chronological work history details."
    )
    projects: List[ProjectItem] = Field(
        default_factory=list,
        description="Personal, professional, or academic projects."
    )
    education: List[EducationItem] = Field(
        default_factory=list,
        description="Educational qualifications."
    )
    certifications: List[str] = Field(
        default_factory=list,
        description="Certifications and licenses obtained."
    )
    inferred_skills: List[str] = Field(
        default_factory=list,
        description="Skills inferred from work experience or projects when explicit skills are missing."
    )
    raw_text: str = Field(
        default="",
        description="The raw unformatted text extracted from the document."
    )
    parse_warnings: List[str] = Field(
        default_factory=list,
        description="Warnings or parsing errors encountered during ingestion."
    )

class JDIntelligence(BaseModel):
    """
    Structured intelligence extracted by the LLM from a Job Description.
    """
    model_config = GLOBAL_CONFIG

    job_title: str = Field(
        ...,
        min_length=1,
        description="Target job title as parsed from the Job Description."
    )
    must_have_skills: List[str] = Field(
        default_factory=list,
        description="Hard skills explicitly marked as mandatory or required."
    )
    good_to_have_skills: List[str] = Field(
        default_factory=list,
        description="Secondary, optional, or preferred skills."
    )
    soft_skills: List[str] = Field(
        default_factory=list,
        description="Soft skills, collaboration, and communication keywords."
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Important keywords, tools, or methodologies to match."
    )
    seniority_level: Optional[str] = Field(
        default=None,
        description="Seniority level (e.g. Junior, Mid, Senior, Lead)."
    )
    conflicts_detected: List[str] = Field(
        default_factory=list,
        description="Conflicts or contradictions parsed in the JD requirements."
    )

class MatchResult(BaseModel):
    """
    Result of aligning a parsed Resume against parsed JD Intelligence.
    """
    model_config = GLOBAL_CONFIG

    matched_skills: List[str] = Field(
        default_factory=list,
        description="List of candidate skills that overlap with JD requirements."
    )
    missing_skills: List[str] = Field(
        default_factory=list,
        description="Important JD skills missing from the candidate's resume."
    )
    matched_projects: List[str] = Field(
        default_factory=list,
        description="Projects in the resume that match the job context."
    )
    weak_sections: List[str] = Field(
        default_factory=list,
        description="Resume sections that are thin or lack alignment with the JD."
    )
    keyword_coverage_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="The calculated keyword overlap percentage between JD and resume (0.0 to 100.0)."
    )

class RecommendationPlan(BaseModel):
    """
    Actionable recipe for how to rewrite/customize the resume.
    """
    model_config = GLOBAL_CONFIG

    rewrite_summary: bool = Field(
        default=False,
        description="Flag indicating if the summary needs restructuring."
    )
    rewrite_experience_indices: List[int] = Field(
        default_factory=list,
        description="Indices of work experience items to rewrite/rephrase."
    )
    reorder_projects: bool = Field(
        default=False,
        description="Flag indicating if projects should be re-sequenced for relevance."
    )
    skills_to_highlight: List[str] = Field(
        default_factory=list,
        description="Skills that must be given high visibility in the summary or skills block."
    )
    missing_keywords: List[str] = Field(
        default_factory=list,
        description="Missing JD-centric keywords to inject during rewrite."
    )
    reasoning: str = Field(
        ...,
        min_length=1,
        description="Human-readable justification or roadmap for the tailoring plan."
    )

class RewriteResult(BaseModel):
    """
    Output of applying a RecommendationPlan to customize the resume.
    """
    model_config = GLOBAL_CONFIG

    updated_resume: ResumeDocument = Field(
        ...,
        description="The customized ResumeDocument with rewrites applied."
    )
    sections_touched: List[str] = Field(
        default_factory=list,
        description="Names of the sections modified (e.g. 'summary', 'experience')."
    )
    raw_llm_output: str = Field(
        ...,
        min_length=1,
        description="Raw output response text returned from the LLM provider."
    )

class ValidationReport(BaseModel):
    """
    Result of comparing the updated resume back to the original for honesty and style checks.
    """
    model_config = GLOBAL_CONFIG

    passed: bool = Field(
        ...,
        description="True if the customization passes all safety, honesty, and format validations."
    )
    violations: List[str] = Field(
        default_factory=list,
        description="List of safety or stylistic policy violations found."
    )
    diff_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="High-level changes diff structured per section."
    )

class ConfidenceScore(BaseModel):
    """
    A comprehensive assessment of customization quality and alignment.
    """
    model_config = GLOBAL_CONFIG

    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Overall pipeline confidence score (0 to 100)."
    )
    jd_match_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Initial alignment match score against the JD (0 to 100)."
    )
    rewrite_quality_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Evaluation of rewriting fluency and keywords density (0 to 100)."
    )
    validation_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Truthfulness and formatting validation compliance score (0 to 100)."
    )
    ats_improvement_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Estimated improvements to ATS keyword indexing scores (0 to 100)."
    )
    needs_human_review: bool = Field(
        ...,
        description="Flag indicating if high risk shifts require manual review."
    )
    explanation: str = Field(
        ...,
        min_length=1,
        description="Detailed text explaining the breakdown of confidence metrics."
    )
