import io
import os
import re
import tempfile
import unicodedata
from typing import Literal, Optional, List
import docx
from docx.text.paragraph import Paragraph as DocxParagraph
from docx.table import Table as DocxTable
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.models.schema import ResumeDocument

# Try loading Windows COM pywin32 and pdf2docx libraries for 100% layout preservation
try:
    import pythoncom
    import win32com.client
    from pdf2docx import Converter
    HAS_LAYOUT_PRESERVATION = True
except ImportError:
    HAS_LAYOUT_PRESERVATION = False

def convert_pdf_to_docx(pdf_bytes: bytes) -> bytes:
    """
    Converts PDF bytes into DOCX bytes using the pdf2docx library.
    Uses temporary files for disk operations.
    """
    fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, 'wb') as temp_pdf:
            temp_pdf.write(pdf_bytes)
            
        docx_path = pdf_path.replace(".pdf", ".docx")
        try:
            cv = Converter(pdf_path)
            cv.convert(docx_path, start=0, end=None)
            cv.close()
            
            with open(docx_path, "rb") as f:
                docx_bytes = f.read()
            return docx_bytes
        finally:
            if os.path.exists(docx_path):
                try:
                    os.remove(docx_path)
                except Exception:
                    pass
    finally:
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass
    raise RuntimeError("Failed to convert PDF to DOCX")

def convert_docx_to_pdf(docx_bytes: bytes) -> bytes:
    """
    Converts DOCX bytes to PDF bytes headlessly using the Microsoft Word COM API on Windows.
    """
    fd, docx_path = tempfile.mkstemp(suffix=".docx")
    try:
        with os.fdopen(fd, 'wb') as temp_docx:
            temp_docx.write(docx_bytes)
            
        pdf_path = docx_path.replace(".docx", ".pdf")
        
        word = None
        try:
            pythoncom.CoInitialize()
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            doc = word.Documents.Open(docx_path)
            # Save as PDF (wdFormatPDF = 17)
            doc.SaveAs(pdf_path, FileFormat=17)
            doc.Close()
        finally:
            if word is not None:
                word.Quit()
            pythoncom.CoUninitialize()
            
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        return pdf_bytes
    finally:
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass
        if os.path.exists(docx_path):
            try:
                os.remove(docx_path)
            except Exception:
                pass
    raise RuntimeError("Failed to convert DOCX to PDF")

def normalize_text_for_match(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text)
    text = text.strip()
    text = re.sub(r'^[\s\-*•o§\d\.\(\)]+', '', text)
    text = re.sub(r'[^a-zA-Z0-9]', '', text)
    return text.lower()

def is_bullet_match(bullet_text: str, para_text: str) -> bool:
    norm_b = normalize_text_for_match(bullet_text)
    norm_p = normalize_text_for_match(para_text)
    if not norm_b or not norm_p:
        return False
    if norm_b == norm_p:
        return True
    if norm_b in norm_p or norm_p in norm_b:
        len_diff = abs(len(norm_b) - len(norm_p))
        return len_diff < 15 or len_diff / max(len(norm_b), len(norm_p)) < 0.3
    return False

def insert_paragraph_after(paragraph, text="", style=None):
    parent = paragraph._element.getparent()
    new_p = paragraph._parent.add_paragraph(text, style=style or paragraph.style)
    idx = parent.index(paragraph._element)
    parent.insert(idx + 1, new_p._element)
    return new_p

def replace_paragraph_text_preserving_prefix(p, new_text: str):
    # 1. Decompose new_text into prefix and content
    new_prefix_match = re.match(r'^([\s\-*•o§\d\.\(\)\t]*)(.*)$', new_text)
    new_prefix = new_prefix_match.group(1) if new_prefix_match else ""
    clean_new_text = new_prefix_match.group(2).strip() if new_prefix_match else new_text.strip()
    
    # 2. Decompose original paragraph text into prefix and content
    orig_text = p.text
    orig_prefix_match = re.match(r'^[\s\-*•o§\d\.\(\)\t]+', orig_text)
    prefix_str = orig_prefix_match.group(0) if orig_prefix_match else ""
    
    # Adjust prefix if the original didn't have trailing whitespace, but the new one does.
    # This prevents squashing text against bullet points.
    if prefix_str and not re.search(r'\s$', prefix_str):
        new_spacing_match = re.search(r'\s+$', new_prefix)
        if new_spacing_match:
            prefix_str += new_spacing_match.group(0)
            
    # If the original paragraph has no runs, just set the text directly
    if not p.runs:
        p.text = prefix_str + clean_new_text
        return

    # 3. Locate which runs correspond to the prefix
    prefix_len = len(prefix_str)
    accumulated_len = 0
    prefix_runs_count = 0
    
    for run in p.runs:
        run_text_len = len(run.text)
        if accumulated_len + run_text_len <= prefix_len:
            accumulated_len += run_text_len
            prefix_runs_count += 1
        else:
            break
            
    # Now, prefix_runs_count tells us how many runs at the start are purely prefix.
    # We leave those runs completely untouched to preserve their formatting and spacing!
    # For the remaining runs, we put the new content in the first content run, and clear others.
    if prefix_runs_count < len(p.runs):
        first_content_run = p.runs[prefix_runs_count]
        run_prefix = prefix_str[accumulated_len:prefix_len]
        first_content_run.text = run_prefix + clean_new_text
        
        for r in p.runs[prefix_runs_count + 1:]:
            r.text = ""
    else:
        # All runs were part of the prefix (edge case). Just append to the last run.
        remaining_part = prefix_str[accumulated_len:prefix_len]
        p.runs[-1].text = p.runs[-1].text + remaining_part + clean_new_text

def iter_block_items(parent):
    if isinstance(parent, docx.document.Document):
        parent_elm = parent.element.body
    elif isinstance(parent, docx.table._Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("Unsupported parent type")

    for child in parent_elm.iterchildren():
        if child.tag.endswith('p'):
            yield DocxParagraph(child, parent)
        elif child.tag.endswith('tbl'):
            table = DocxTable(child, parent)
            for row in table.rows:
                for cell in row.cells:
                    yield from iter_block_items(cell)

def render(
    original_file_bytes: bytes,
    original_filename: str,
    rewritten: ResumeDocument,
    fmt: Literal["pdf", "docx", "txt"],
    original_doc: Optional[ResumeDocument] = None
) -> bytes:
    """
    Renders the customized ResumeDocument back into the requested format (pdf, docx, or txt).
    Always falls back to plain text if a rendering error occurs.
    """
    fmt = fmt.lower().strip()
    is_pdf = original_filename.lower().endswith(".pdf")
    
    try:
        # Step 1: Normalize input to DOCX bytes for in-place text run replacement
        if is_pdf:
            if HAS_LAYOUT_PRESERVATION and original_file_bytes:
                try:
                    docx_bytes = convert_pdf_to_docx(original_file_bytes)
                except Exception as e:
                    print(f"pdf2docx conversion failed: {e}")
                    docx_bytes = b""
            else:
                # Fallback directly to text if layout preservation engine imports are not available
                docx_bytes = b""
        else:
            docx_bytes = original_file_bytes

        if fmt == "docx":
            if is_pdf and not docx_bytes:
                # If they want docx from a PDF and conversion wasn't available, fail over to TXT
                raise ValueError("PDF to DOCX conversion is not supported on this platform.")
            return _render_docx(docx_bytes, rewritten, original_doc)
            
        elif fmt == "pdf":
            if docx_bytes and HAS_LAYOUT_PRESERVATION:
                try:
                    # Customize DOCX in-place (keeps layout, fonts, borders)
                    customized_docx_bytes = _render_docx(docx_bytes, rewritten, original_doc)
                    # Headless MS Word DOCX -> PDF conversion (keeps layout, fonts, borders 100%)
                    return convert_docx_to_pdf(customized_docx_bytes)
                except Exception as com_err:
                    print(f"Word COM PDF rendering failed, falling back to ReportLab reconstruction: {com_err}")
            
            # Standard fallback layout-approximated PDF (e.g. on Linux or if Word is missing)
            return _render_pdf(original_file_bytes, rewritten)
            
        elif fmt == "txt":
            return _render_txt(rewritten)
        else:
            raise ValueError(f"Unsupported format: {fmt}")
    except Exception as e:
        print(f"Rendering failed: {e}. Falling back to plain text.")
        # Guaranteed-to-work fallback if any rendering throws
        return _render_txt(rewritten)


def _render_docx(
    original_bytes: bytes,
    rewritten: ResumeDocument,
    original_doc: Optional[ResumeDocument] = None
) -> bytes:
    """
    DOCX rendering: Opens original document via python-docx, searches for paragraphs 
    that correspond to modified sections, and updates run texts while preserving styles.
    """
    doc = docx.Document(io.BytesIO(original_bytes))
    
    # 1. Parse original document on the fly if not provided
    if not original_doc and original_bytes:
        from app.services.parser import parse_resume
        from app.services.normalizer import normalize
        try:
            parsed = parse_resume(original_bytes, "original.docx")
            original_doc = normalize(parsed)
        except Exception as e:
            print(f"Failed to parse original docx on the fly: {e}")
            original_doc = None

    # 2. Iterate through all paragraphs in document order
    all_paras = list(iter_block_items(doc))
    matched_para_ids = set()

    # 3. Perform summary replacement
    summary_replaced = False
    if original_doc and original_doc.summary and rewritten.summary:
        orig_summary_lines = [line.strip() for line in original_doc.summary.split('\n') if line.strip()]
        new_summary_lines = [line.strip() for line in rewritten.summary.split('\n') if line.strip()]
        
        # Match each original summary paragraph in the doc
        matched_summary_paras = []
        for line in orig_summary_lines:
            norm_line = normalize_text_for_match(line)
            for p in all_paras:
                if id(p) in matched_para_ids:
                    continue
                # Skip list bullets when matching summary
                is_bullet = p.style.name.startswith("List") or p.text.strip().startswith(("-", "*", "•"))
                if is_bullet:
                    continue
                norm_p = normalize_text_for_match(p.text)
                if norm_line and norm_p and (norm_line == norm_p or norm_line in norm_p or norm_p in norm_line):
                    matched_summary_paras.append(p)
                    matched_para_ids.add(id(p))
                    break
        
        if matched_summary_paras:
            # Replace matched summary paragraphs
            for i in range(min(len(matched_summary_paras), len(new_summary_lines))):
                p = matched_summary_paras[i]
                new_text = new_summary_lines[i]
                replace_paragraph_text_preserving_prefix(p, new_text)
            
            # If new summary has fewer paragraphs, delete remaining matched paragraphs
            if len(matched_summary_paras) > len(new_summary_lines):
                for i in range(len(new_summary_lines), len(matched_summary_paras)):
                    p = matched_summary_paras[i]
                    parent = p._element.getparent()
                    if parent is not None:
                        parent.remove(p._element)
            
            # If new summary has more paragraphs, insert them after the last matched paragraph
            elif len(new_summary_lines) > len(matched_summary_paras):
                last_p = matched_summary_paras[-1]
                current_p = last_p
                for i in range(len(matched_summary_paras), len(new_summary_lines)):
                    new_p = insert_paragraph_after(current_p, new_summary_lines[i])
                    current_p = new_p
            
            summary_replaced = True

    # Fallback for summary if not replaced by content match
    if not summary_replaced and rewritten.summary:
        summary_clean = rewritten.summary.strip()
        # Find first paragraph that fits summary heuristic
        for p in all_paras:
            if id(p) in matched_para_ids:
                continue
            text = p.text.strip()
            if len(text) > 40 and not text.isupper() and not any(kw in text.lower() for kw in ["experience", "education", "skills", "projects", "certifications"]):
                replace_paragraph_text_preserving_prefix(p, summary_clean)
                matched_para_ids.add(id(p))
                summary_replaced = True
                break

    # 4. Perform experience bullets replacement
    experience_replaced = False
    if original_doc and original_doc.experience and rewritten.experience and len(original_doc.experience) == len(rewritten.experience):
        for idx in range(len(rewritten.experience)):
            orig_exp = original_doc.experience[idx]
            new_exp = rewritten.experience[idx]
            
            if orig_exp.bullets != new_exp.bullets:
                # Find paragraphs matching the original bullets
                matched_bullet_paras = []
                for b in orig_exp.bullets:
                    for p in all_paras:
                        if id(p) in matched_para_ids:
                            continue
                        if is_bullet_match(b, p.text):
                            matched_bullet_paras.append(p)
                            matched_para_ids.add(id(p))
                            break
                
                if matched_bullet_paras:
                    # Replace matched bullet paragraphs
                    for i in range(min(len(matched_bullet_paras), len(new_exp.bullets))):
                        p = matched_bullet_paras[i]
                        new_text = new_exp.bullets[i]
                        replace_paragraph_text_preserving_prefix(p, new_text)
                    
                    # Delete extra bullets
                    if len(matched_bullet_paras) > len(new_exp.bullets):
                        for i in range(len(new_exp.bullets), len(matched_bullet_paras)):
                            p = matched_bullet_paras[i]
                            parent = p._element.getparent()
                            if parent is not None:
                                parent.remove(p._element)
                    
                    # Insert new bullets
                    elif len(new_exp.bullets) > len(matched_bullet_paras):
                        last_p = matched_bullet_paras[-1]
                        current_p = last_p
                        for i in range(len(matched_bullet_paras), len(new_exp.bullets)):
                            new_bullet_text = new_exp.bullets[i]
                            clean_new_text = re.sub(r'^[\s\-*•o§\d\.\(\)]+', '', new_bullet_text).strip()
                            orig_prefix = re.match(r'^[\s\-*•o§\d\.\(\)]+', last_p.text)
                            prefix_str = orig_prefix.group(0) if orig_prefix else ""
                            
                            new_p = insert_paragraph_after(current_p, prefix_str + clean_new_text)
                            current_p = new_p
                    
                    experience_replaced = True

    # Fallback sequential bullet replacement if experience bullets weren't replaced by content match
    # Only run this sequential fallback if the original document is entirely missing experience info
    if not experience_replaced and (not original_doc or not original_doc.experience):
        bullets_to_replace = []
        for exp in rewritten.experience:
            bullets_to_replace.extend(exp.bullets)
            
        bullet_idx = 0
        for p in all_paras:
            if id(p) in matched_para_ids:
                continue
            text = p.text.strip()
            if not text:
                continue
            
            # Match unicode dashes and common bullet markers
            is_bullet = p.style.name.startswith("List") or text.startswith(("-", "*", "•", "–", "—"))
            if is_bullet and bullet_idx < len(bullets_to_replace):
                new_bullet_text = bullets_to_replace[bullet_idx]
                replace_paragraph_text_preserving_prefix(p, new_bullet_text)
                matched_para_ids.add(id(p))
                bullet_idx += 1

    out_buf = io.BytesIO()
    doc.save(out_buf)
    return out_buf.getvalue()

def _render_pdf(original_bytes: bytes, rewritten: ResumeDocument) -> bytes:
    """
    PDF rendering: Fallback generator that reconstructs a professional, visually clean 
    document using reportlab platypus templates, mimicking the candidate's original resume layout.
    """
    pdf_buf = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buf,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom elegant styles
    title_style = ParagraphStyle(
        'ResumeTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1A202C"),
        alignment=1, # Center
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'ResumeSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#4A5568"),
        alignment=1, # Center
        spaceAfter=8
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1A202C"),
        spaceBefore=10,
        spaceAfter=2,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'ResumeBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=4
    )
    
    bullet_style = ParagraphStyle(
        'ResumeBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#2D3748"),
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=2
    )
    
    story = []
    
    # Divider drawing utility (colWidths matching 504pt printable area)
    def add_divider():
        t = Table([['']], colWidths=[504])
        t.setStyle(TableStyle([
            ('LINEBELOW', (0,0), (-1,-1), 0.75, colors.HexColor("#CBD5E0")),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(t)
        story.append(Spacer(1, 4))
        
    def add_section(title):
        story.append(Paragraph(title, section_heading))
        add_divider()
    
    # Header block: centering Name and Contact details
    header_name = rewritten.name.strip() if rewritten.name else "Curriculum Vitae"
    story.append(Paragraph(header_name, title_style))
    
    if rewritten.contact_info:
        contact_bar = "  |  ".join(rewritten.contact_info)
        story.append(Paragraph(contact_bar, subtitle_style))
        story.append(Spacer(1, 4))
        add_divider()
    else:
        story.append(Spacer(1, 10))
        
    # Summary Section
    if rewritten.summary:
        add_section("PROFESSIONAL SUMMARY")
        story.append(Paragraph(rewritten.summary, body_style))
        story.append(Spacer(1, 6))
        
    # Skills Section
    if rewritten.skills:
        add_section("TECHNICAL SKILLS")
        skills_str = ", ".join(rewritten.skills)
        story.append(Paragraph(skills_str, body_style))
        story.append(Spacer(1, 6))
        
    # Experience Section
    if rewritten.experience:
        add_section("PROFESSIONAL EXPERIENCE")
        for exp in rewritten.experience:
            header_text = f"<b>{exp.company}</b> — {exp.title} ({exp.start_date} - {exp.end_date or 'Present'})"
            story.append(Paragraph(header_text, body_style))
            for bullet in exp.bullets:
                story.append(Paragraph(f"&bull; {bullet}", bullet_style))
            story.append(Spacer(1, 4))
            
    # Projects Section
    if rewritten.projects:
        add_section("PROJECTS")
        for proj in rewritten.projects:
            header_text = f"<b>{proj.name}</b> ({', '.join(proj.tech_stack)})"
            story.append(Paragraph(header_text, body_style))
            for bullet in proj.bullets:
                story.append(Paragraph(f"&bull; {bullet}", bullet_style))
            story.append(Spacer(1, 4))
            
    # Education Section
    if rewritten.education:
        add_section("EDUCATION")
        for edu in rewritten.education:
            edu_text = f"<b>{edu.institution}</b> — {edu.degree} ({edu.start_date} - {edu.end_date or 'Present'})"
            story.append(Paragraph(edu_text, body_style))
            story.append(Spacer(1, 4))
            
    doc.build(story)
    return pdf_buf.getvalue()


def _render_txt(rewritten: ResumeDocument) -> bytes:
    """
    TXT rendering: Serializes the ResumeDocument into clean plain text lines.
    """
    lines = []
    
    if rewritten.summary:
        lines.append("SUMMARY")
        lines.append("=" * 7)
        lines.append(rewritten.summary)
        lines.append("")
        
    if rewritten.skills:
        lines.append("TECHNICAL SKILLS")
        lines.append("=" * 16)
        lines.append(", ".join(rewritten.skills))
        lines.append("")
        
    if rewritten.experience:
        lines.append("PROFESSIONAL EXPERIENCE")
        lines.append("=" * 23)
        for exp in rewritten.experience:
            lines.append(f"{exp.company} - {exp.title} ({exp.start_date} - {exp.end_date or 'Present'})")
            for b in exp.bullets:
                lines.append(f"  * {b}")
            lines.append("")
            
    if rewritten.projects:
        lines.append("PROJECTS")
        lines.append("=" * 8)
        for proj in rewritten.projects:
            lines.append(f"{proj.name} ({', '.join(proj.tech_stack)})")
            for b in proj.bullets:
                lines.append(f"  * {b}")
            lines.append("")
            
    if rewritten.education:
        lines.append("EDUCATION")
        lines.append("=" * 9)
        for edu in rewritten.education:
            lines.append(f"{edu.institution} - {edu.degree} ({edu.start_date} - {edu.end_date or 'Present'})")
            lines.append("")
            
    if rewritten.certifications:
        lines.append("CERTIFICATIONS")
        lines.append("=" * 14)
        for cert in rewritten.certifications:
            lines.append(f"  * {cert}")
        lines.append("")

    return "\n".join(lines).encode("utf-8")
