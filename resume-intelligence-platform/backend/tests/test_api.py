import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_customize_endpoint_validation_empty_jd():
    # Attempt request with empty JD (whitespace check)
    response = client.post(
        "/api/customize",
        data={"jd_text": "   "},
        files={"file": ("resume.pdf", b"%PDF-1.4...", "application/pdf")}
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ValidationError"
    assert "empty" in response.json()["detail"].lower()

def test_customize_endpoint_validation_short_jd():
    # Attempt request with JD < 100 characters
    response = client.post(
        "/api/customize",
        data={"jd_text": "Need python developer"},
        files={"file": ("resume.pdf", b"%PDF-1.4...", "application/pdf")}
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ValidationError"
    assert "at least 100 characters" in response.json()["detail"].lower()

def test_customize_endpoint_validation_unsupported_media():
    response = client.post(
        "/api/customize",
        data={"jd_text": "Need python developer who has experience in FastAPI and React. This role is remote and senior level." * 5},
        files={"file": ("resume.txt", b"plain text content", "text/plain")}
    )
    assert response.status_code == 415
    assert response.json()["error"] == "UnsupportedMediaType"

def test_customize_endpoint_validation_file_oversized():
    # Generate 6MB file stream
    oversized_bytes = b"0" * (6 * 1024 * 1024)
    response = client.post(
        "/api/customize",
        data={"jd_text": "Need python developer who has experience in FastAPI and React. This role is remote and senior level." * 5},
        files={"file": ("resume.pdf", oversized_bytes, "application/pdf")}
    )
    assert response.status_code == 413
    assert response.json()["error"] == "PayloadTooLarge"

@patch("app.services.rewriter.genai.Client")
def test_customize_endpoint_success(mock_client_class):
    # Setup rewriter mock
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    
    mock_response.text = '{"summary": "Structured LLM Summary Rewrite", "experience_bullets": {}}'
    mock_chat.send_message.return_value = mock_response
    mock_client.chats.create.return_value = mock_chat
    mock_client_class.return_value = mock_client
    
    # Generate a small valid PDF bytes representation
    from tests.test_parser import create_valid_pdf
    pdf_bytes = create_valid_pdf("""
Work Experience
Active Corp | Software Engineer | 2020 - Present
- Wrote software in Python.
""")
    
    jd_content = (
        "We are looking for a Senior Software Engineer. "
        "The ideal candidate must know Python and FastAPI. "
        "Requirements: "
        "- 3+ years experience with Python and backend development. "
        "- React and Docker are nice to have. "
        "This is a full time position."
    )
    
    response = client.post(
        "/api/customize",
        data={"jd_text": jd_content},
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "resume" in data
    assert "match" in data
    assert "rewrite" in data
    assert "validation" in data
    assert "confidence" in data
    assert "customized_resume" in data
    assert "reason" in data
    
    # Assert parsed/rewritten results are present and validated
    assert data["validation"]["passed"] is True
    assert data["reason"] is None
    assert data["customized_resume"] is not None
    assert data["resume"]["summary"] == "Structured LLM Summary Rewrite"
    assert "Python" in data["match"]["matched_skills"]
    assert data["plan"]["rewrite_summary"] is True  # summary weak, trigger rewrite

@patch("app.services.rewriter.genai.Client")
def test_customize_endpoint_validation_failure_fallback(mock_client_class):
    # Setup rewriter mock returning a technology hallucination ("Kafka")
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    
    # "Kafka" is a technology keyword not present in the original resume text
    mock_response.text = '{"summary": "A fabricated summary.", "experience_bullets": {"0": ["Implemented Kafka streams."]}}'
    mock_chat.send_message.return_value = mock_response
    mock_client.chats.create.return_value = mock_chat
    mock_client_class.return_value = mock_client
    
    from tests.test_parser import create_valid_pdf
    pdf_bytes = create_valid_pdf("""
Skills: Python

Work Experience
Active Corp | Software Engineer | 2020 - Present
- Worked on web servers.
""")
    
    jd_content = (
        "We are looking for a Senior Software Engineer. "
        "The ideal candidate must know Python and FastAPI. "
        "Requirements: "
        "- 3+ years experience with Python and backend development."
        "This is a full time position."
    )
    
    response = client.post(
        "/api/customize",
        data={"jd_text": jd_content},
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["validation"]["passed"] is False
    assert any("fabricated technology 'kafka'" in v.lower() for v in data["validation"]["violations"])
    assert data["customized_resume"] is None
    assert "factual validation failed" in data["reason"].lower()
    
    # The output resume should have been discarded and replaced with the original parsed/normalized resume
    # The original resume summary is kept (which will not match the LLM's fabricated summary)
    assert data["resume"]["summary"] != "A fabricated summary."
    # Ensure the experience bullets are untouched (still original, not Kafka)
    assert data["resume"]["experience"][0]["bullets"] == ["Worked on web servers."]

@patch("app.services.rewriter.genai.Client")
def test_customize_endpoint_low_confidence_reject(mock_client_class):
    # Setup rewriter mock
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    
    mock_response.text = '{"summary": "Low confidence summary.", "experience_bullets": {}}'
    mock_chat.send_message.return_value = mock_response
    mock_client.chats.create.return_value = mock_chat
    mock_client_class.return_value = mock_client
    
    # Original resume only has Python
    from tests.test_parser import create_valid_pdf
    pdf_bytes = create_valid_pdf("""
Skills: Python

Work Experience
Active Corp | Software Engineer | 2020 - Present
- Worked on Python scripts.
""")
    
    # JD lists completely different technologies (no overlap)
    jd_content = (
        "We are looking for a Senior React and Go Developer. "
        "The ideal candidate must know React, Go, and Kubernetes. "
        "Requirements: "
        "- 3+ years experience with React, Go, and Kubernetes. "
        "- AWS is nice to have."
    )
    
    response = client.post(
        "/api/customize",
        data={"jd_text": jd_content},
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Validation passes, but confidence is low (< 60.0%) because of 0% keyword match
    assert data["validation"]["passed"] is True
    assert data["confidence"]["overall_confidence"] < 60.0
    assert data["customized_resume"] is None
    assert "below the minimum threshold of 60.0%" in data["reason"]

@patch("app.services.rewriter.genai.Client")
def test_download_resume_workflow(mock_client_class):
    # 1. Setup mock LLM success
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"summary": "Aligned Python summary.", "experience_bullets": {}}'
    mock_chat.send_message.return_value = mock_response
    mock_client.chats.create.return_value = mock_chat
    mock_client_class.return_value = mock_client
    
    from tests.test_parser import create_valid_pdf
    pdf_bytes = create_valid_pdf("""
Work Experience
Active Corp | Software Engineer | 2020 - Present
- Wrote code in Python.
""")
    
    # 2. Call customize to cache it
    response = client.post(
        "/api/customize",
        data={"jd_text": "Need python developer who has experience in FastAPI and React. This role is remote and senior level." * 5},
        files={"file": ("my_resume.pdf", pdf_bytes, "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    job_id = data["job_id"]
    assert job_id is not None
    
    # 3. Download as PDF
    pdf_resp = client.get(f"/api/download/{job_id}?format=pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert "my_resume_customized.pdf" in pdf_resp.headers["content-disposition"]
    assert pdf_resp.content.startswith(b"%PDF-")
    
    # 4. Download as TXT
    txt_resp = client.get(f"/api/download/{job_id}?format=txt")
    assert txt_resp.status_code == 200
    assert "text/plain" in txt_resp.headers["content-type"]
    assert "my_resume_customized.txt" in txt_resp.headers["content-disposition"]
    assert b"SUMMARY" in txt_resp.content

def test_download_resume_invalid_job():
    response = client.get("/api/download/nonexistent-job-uuid?format=pdf")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
