import pytest
from unittest.mock import MagicMock, patch
from app.models.schema import (
    ResumeDocument, ExperienceItem, JDIntelligence, RecommendationPlan
)
from app.services.rewriter import rewrite, build_prompt

def test_build_prompt_structure():
    resume = ResumeDocument(
        summary="Old Summary",
        experience=[
            ExperienceItem(company="A", title="SWE", start_date="2020", bullets=["Bullet 1"])
        ]
    )
    jd = JDIntelligence(job_title="SWE", must_have_skills=["Python"], keywords=["Python"])
    plan = RecommendationPlan(
        rewrite_summary=True,
        rewrite_experience_indices=[0],
        skills_to_highlight=["Python"],
        reasoning="Test"
    )
    
    prompt = build_prompt(resume, jd, plan)
    assert "SUMMARY TO REWRITE" in prompt
    assert "WORK EXPERIENCE BULLETS TO REWRITE" in prompt
    assert "A - SWE" in prompt

@patch("app.services.rewriter.genai.Client")
def test_rewrite_merge_logic_respects_plan_summary_only(mock_client_class):
    # Setup mocks
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    
    mock_response.text = '{"summary": "New Cool Summary", "experience_bullets": {"0": ["Attempted bullet rewrite"]}}'
    mock_chat.send_message.return_value = mock_response
    mock_client.chats.create.return_value = mock_chat
    mock_client_class.return_value = mock_client
    
    resume = ResumeDocument(
        summary="Old Summary",
        experience=[
            ExperienceItem(
                company="Google",
                title="SWE",
                start_date="2020-01",
                end_date="Present",
                bullets=["Keep this bullet untouched"]
            )
        ]
    )
    
    jd = JDIntelligence(job_title="SWE", must_have_skills=["Python"], keywords=["Python"])
    
    # Plan only triggers summary rewrite
    plan = RecommendationPlan(
        rewrite_summary=True,
        rewrite_experience_indices=[],  # Experience index 0 is NOT in plan
        skills_to_highlight=["Python"],
        reasoning="Test reasoning"
    )
    
    result = rewrite(resume, jd, plan)
    
    # Summary should be updated
    assert result.updated_resume.summary == "New Cool Summary"
    assert "summary" in result.sections_touched
    
    # Experience bullet should NOT be updated because it wasn't in the plan, even though LLM output had it
    assert result.updated_resume.experience[0].bullets == ["Keep this bullet untouched"]
    assert "experience_0" not in result.sections_touched

@patch("app.services.rewriter.genai.Client")
def test_rewrite_merge_logic_respects_plan_experience_only(mock_client_class):
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    
    mock_response.text = '{"summary": "Fake Summary Rewrite", "experience_bullets": {"1": ["Rewritten Bullet for idx 1"]}}'
    mock_chat.send_message.return_value = mock_response
    mock_client.chats.create.return_value = mock_chat
    mock_client_class.return_value = mock_client
    
    resume = ResumeDocument(
        summary="Original summary text",
        experience=[
            ExperienceItem(
                company="Google",
                title="SWE",
                start_date="2020-01",
                end_date="Present",
                bullets=["Untouched bullet idx 0"]
            ),
            ExperienceItem(
                company="Amazon",
                title="SWE",
                start_date="2018-01",
                end_date="2020-01",
                bullets=["Old bullet idx 1"]
            )
        ]
    )
    
    jd = JDIntelligence(job_title="SWE", must_have_skills=["Python"], keywords=["Python"])
    
    # Plan only triggers experience index 1 rewrite
    plan = RecommendationPlan(
        rewrite_summary=False,  # Summary NOT in plan
        rewrite_experience_indices=[1],  # Only index 1 in plan
        skills_to_highlight=["Python"],
        reasoning="Test reasoning"
    )
    
    result = rewrite(resume, jd, plan)
    
    # Summary must remain untouched
    assert result.updated_resume.summary == "Original summary text"
    assert "summary" not in result.sections_touched
    
    # Experience 0 must remain untouched
    assert result.updated_resume.experience[0].bullets == ["Untouched bullet idx 0"]
    assert "experience_0" not in result.sections_touched
    
    # Experience 1 should be rewritten
    assert result.updated_resume.experience[1].bullets == ["Rewritten Bullet for idx 1"]
    assert "experience_1" in result.sections_touched
