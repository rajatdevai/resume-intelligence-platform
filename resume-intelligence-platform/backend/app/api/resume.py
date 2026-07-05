import os
import uuid
from fastapi import APIRouter, File, UploadFile, Form, status, Response, HTTPException
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.exceptions import ParserError, ValidationError, LLMError
from app.services.parser import parse_resume
from app.services.normalizer import normalize
from app.services.jd_engine import analyze_jd, chunk_if_needed
from app.services.matcher import match
from app.services.recommender import recommend
from app.services.rewriter import rewrite
from app.services.validator import validate
from app.services.confidence import score
from app.services.renderer import render

# Short-lived in-memory cache mapping job_id -> metadata
RENDER_CACHE = {}

router = APIRouter(prefix="/api", tags=["resume"])

@router.post("/customize")
async def customize_resume(
    file: UploadFile = File(...),
    jd_text: str = Form(...)
):
    """
    Orchestrates the resume customization pipeline:
    1. Validates file size and format, and JD text length.
    2. Parses the resume document (PDF/DOCX).
    3. Normalizes terms and date fields.
    4. Evaluates the Job Description.
    5. Matches candidate qualifications to job criteria.
    6. Formulates an optimization recommendation plan.
    7. Generates LLM-backed revisions for targeted sections.
    """
    # 1. Job Description Validation
    jd_clean = jd_text.strip() if jd_text else ""
    if not jd_clean:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "ValidationError", "detail": "Job Description text cannot be empty."}
        )
    if len(jd_clean) < 100:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "ValidationError", "detail": "Job Description text is too short (must be at least 100 characters)."}
        )

    # 2. File Format Validation
    filename = file.filename or ""
    ext = os.path.splitext(filename.lower())[1]
    if ext not in [".pdf", ".docx"]:
        return JSONResponse(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            content={"error": "UnsupportedMediaType", "detail": "Unsupported file format. Only PDF and DOCX files are allowed."}
        )

    # 3. File Size Validation (streamed block check)
    file_bytes = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"error": "PayloadTooLarge", "detail": f"File size exceeds the maximum limit of {settings.MAX_UPLOAD_MB}MB."}
        )

    # 4. Pipeline Execution
    try:
        # Step 1: Raw extraction
        parsed_doc = parse_resume(file_bytes, filename)
        
        # Step 2: Clean and normalize
        normalized_doc = normalize(parsed_doc)
        
        # Step 3: Chunk and analyze JD
        jd_chunk = chunk_if_needed(jd_clean)
        jd_intel = analyze_jd(jd_chunk)
        
        # Step 4: Run skill matching
        match_result = match(normalized_doc, jd_intel)
        
        # Step 5: Draft recommendation plans
        plan = recommend(normalized_doc, jd_intel, match_result)
        
        # Step 6: Generate LLM customized rewrites
        rewrite_result = rewrite(normalized_doc, jd_intel, plan)
        
        # Step 7: Factual validation
        validation_report = validate(normalized_doc, rewrite_result.updated_resume, plan)
        
        # Step 8: Confidence scoring
        confidence_report = score(match_result, validation_report, normalized_doc, rewrite_result.updated_resume, plan)
        
        # Decide customized resume presence based on validation and score thresholds
        validation_failed = not validation_report.passed
        low_confidence = confidence_report.overall_confidence < 60.0
        
        if validation_failed or low_confidence:
            customized_resume = None
            if validation_failed:
                reason = f"Factual validation failed with violations: {', '.join(validation_report.violations)}."
            else:
                reason = f"Pipeline confidence is {confidence_report.overall_confidence:.1f}%, which is below the minimum threshold of 60.0%. Suggestions: Improve JD specificity or resume details."
            final_resume = normalized_doc
        else:
            customized_resume = rewrite_result.updated_resume
            final_resume = rewrite_result.updated_resume
            reason = None
            
        # Generate job_id and store in RENDER_CACHE
        job_id = str(uuid.uuid4())
        RENDER_CACHE[job_id] = {
            "original_bytes": file_bytes,
            "original_filename": filename,
            "original_doc": normalized_doc,
            "rewritten": final_resume
        }
        
        return {
            "job_id": job_id,
            "resume": final_resume,
            "customized_resume": customized_resume,
            "match": match_result,
            "plan": plan,
            "rewrite": rewrite_result,
            "validation": validation_report,
            "confidence": confidence_report,
            "reason": reason
        }
        
    except ParserError as pe:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "ParserError", "detail": pe.message}
        )
    except ValidationError as ve:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "ValidationError", "detail": ve.message}
        )
    except LLMError as le:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"error": "LLMError", "detail": le.message}
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "InternalServerError", "detail": f"An unexpected pipeline error occurred: {str(e)}"}
        )

@router.get("/download/{job_id}")
async def download_resume(
    job_id: str,
    format: str = "pdf"
):
    """
    Downloads the rewritten resume in the specified format (pdf, docx, or txt).
    Fals back to plain text if the requested format fails to render.
    """
    if job_id not in RENDER_CACHE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job customization data not found or has expired."
        )
        
    cache_entry = RENDER_CACHE[job_id]
    original_bytes = cache_entry["original_bytes"]
    original_filename = cache_entry["original_filename"]
    original_doc = cache_entry.get("original_doc")
    rewritten = cache_entry["rewritten"]
    
    fmt = format.lower().strip()
    if fmt not in ["pdf", "docx", "txt"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported format. Only 'pdf', 'docx', and 'txt' are allowed."
        )
        
    # Render customized document bytes
    rendered_bytes = render(original_bytes, original_filename, rewritten, fmt, original_doc)
    
    base_name = os.path.splitext(original_filename)[0]
    download_filename = f"{base_name}_customized.{fmt}"
    
    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain"
    }
    
    return Response(
        content=rendered_bytes,
        media_type=media_types[fmt],
        headers={
            "Content-Disposition": f"attachment; filename=\"{download_filename}\""
        }
    )
