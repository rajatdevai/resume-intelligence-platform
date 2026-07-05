import io
import pytest
from reportlab.pdfgen import canvas
from reportlab.lib.pdfencrypt import StandardEncryption
import docx

from app.core.exceptions import ParserError
from app.services.parser import parse_resume

# Helpers to generate test files in-memory

def create_valid_pdf(content: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    textobj = c.beginText(100, 750)
    for line in content.split('\n'):
        textobj.textLine(line)
    c.drawText(textobj)
    c.showPage()
    c.save()
    return buf.getvalue()

def create_encrypted_pdf(content: str) -> bytes:
    buf = io.BytesIO()
    enc = StandardEncryption("user_password", "owner_password", canPrint=0)
    c = canvas.Canvas(buf, encrypt=enc)
    c.drawString(100, 750, content)
    c.showPage()
    c.save()
    return buf.getvalue()

def create_valid_docx(content: str) -> bytes:
    doc = docx.Document()
    doc.add_paragraph(content)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

# Tests

def test_parse_valid_pdf():
    text_content = """
Work Experience
Google | Software Engineer | Jan 2020 - Present
- Hello, this is a test resume content for pdf parsing.
"""
    file_bytes = create_valid_pdf(text_content)
    
    doc = parse_resume(file_bytes, "my_resume.pdf")
    assert doc.raw_text is not None
    assert "test resume content" in doc.raw_text.lower()
    assert doc.summary == ""
    assert len(doc.skills) == 0

def test_parse_valid_docx():
    text_content = """
Work Experience
Google | Software Engineer | Jan 2020 - Present
- Hello, this is a test resume content for docx parsing.
"""
    file_bytes = create_valid_docx(text_content)
    
    doc = parse_resume(file_bytes, "my_resume.docx")
    assert doc.raw_text is not None
    assert "test resume content" in doc.raw_text.lower()
    assert doc.summary == ""

def test_parse_empty_file():
    with pytest.raises(ParserError) as exc_info:
        parse_resume(b"", "resume.pdf")
    assert "empty file" in str(exc_info.value).lower()

def test_parse_unsupported_file_type():
    with pytest.raises(ParserError) as exc_info:
        parse_resume(b"some content", "resume.txt")
    assert "unsupported file type" in str(exc_info.value).lower()

def test_parse_password_protected_pdf():
    file_bytes = create_encrypted_pdf("Secret resume contents")
    with pytest.raises(ParserError) as exc_info:
        parse_resume(file_bytes, "secured_resume.pdf")
    assert "password-protected" in str(exc_info.value).lower()

def test_parse_corrupted_pdf():
    # Write some junk bytes pretending to be a PDF
    file_bytes = b"%PDF-1.4\n%junk bytes that make pdf reader crash"
    with pytest.raises(ParserError) as exc_info:
        parse_resume(file_bytes, "corrupt.pdf")
    # Should raise corrupted or invalid PDF
    assert "corrupted or invalid" in str(exc_info.value).lower() or "no text could be extracted" in str(exc_info.value).lower()

def test_parse_corrupted_docx():
    file_bytes = b"Junk DOCX bytes"
    with pytest.raises(ParserError) as exc_info:
        parse_resume(file_bytes, "corrupt.docx")
    assert "corrupted or invalid" in str(exc_info.value).lower()

def test_parse_wrapped_bullets():
    text_content = """
PROFESSIONAL EXPERIENCE
Google | Software Engineer | Jan 2020 - Present
- First line of the bullet point that is quite long
and continues on this second line without a bullet prefix
- Second bullet point line
"""
    file_bytes = create_valid_pdf(text_content)
    doc = parse_resume(file_bytes, "resume.pdf")
    
    assert len(doc.experience) == 1
    exp = doc.experience[0]
    assert exp.company == "Google"
    assert exp.title == "Software Engineer"
    assert len(exp.bullets) == 2
    assert "continues on this second line" in exp.bullets[0]
    assert "Second bullet point line" in exp.bullets[1]

def test_parse_header_metadata():
    text_content = """
RAJAT SINGH
-91-7701929385 | srajat1685@gmail.com | github.com/rajatdevai | linkedin.com/in/rajat-singh-76b798292

PROFESSIONAL SUMMARY
A highly experienced Software Engineer specializing in AI tooling and platforms.
"""
    file_bytes = create_valid_pdf(text_content)
    doc = parse_resume(file_bytes, "resume.pdf")
    
    assert doc.name == "RAJAT SINGH"
    assert len(doc.contact_info) == 4
    assert "-91-7701929385" in doc.contact_info
    assert "srajat1685@gmail.com" in doc.contact_info
    assert "github.com/rajatdevai" in doc.contact_info
    assert "linkedin.com/in/rajat-singh-76b798292" in doc.contact_info


def test_parse_decorative_section_headers():
    text_content = """
KEY PROJECTS ___________ :
Proj A
- A project with a summary.
EDUCATION ——————————
MIT | CS | 2016 - 2020
"""
    file_bytes = create_valid_pdf(text_content)
    doc = parse_resume(file_bytes, "resume.pdf")
    
    assert len(doc.projects) == 1
    assert doc.projects[0].name == "Proj A"
    assert len(doc.education) == 1
    assert doc.education[0].institution == "MIT"


