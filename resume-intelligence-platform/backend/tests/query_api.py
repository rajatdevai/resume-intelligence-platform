import io
import requests
from reportlab.pdfgen import canvas

def main():
    # 1. Create a minimal PDF in-memory
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf)
    textobj = c.beginText(100, 750)
    textobj.textLine("Work Experience")
    textobj.textLine("Google | Software Engineer | Jan 2020 - Present")
    textobj.textLine("- Built distributed systems in Python.")
    textobj.textLine("- Managed backend databases using PostgreSQL.")
    c.drawText(textobj)
    c.showPage()
    c.save()
    pdf_bytes = pdf_buf.getvalue()

    # 2. Setup payload
    jd_content = (
        "Role: Senior Backend Engineer. "
        "We are looking for a Python and FastAPI expert. "
        "Must have requirements: "
        "- At least 3 years experience with Python. "
        "- Relational databases like Postgres. "
        "Preferred qualifications: "
        "- Knowledge of AWS and Docker is desired."
    )
    
    # 3. Call endpoint
    print("Calling http://127.0.0.1:8000/api/customize ...")
    response = requests.post(
        "http://127.0.0.1:8000/api/customize",
        data={"jd_text": jd_content},
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("\n=== Matched Skills ===")
        print(data["match"]["matched_skills"])
        print("\n=== Missing Skills ===")
        print(data["match"]["missing_skills"])
        print("\n=== Recommendation Reasoning ===")
        print(data["plan"]["reasoning"])
        print("\n=== Rewritten Resume Touched Sections ===")
        print(data["rewrite"]["sections_touched"])
        print("\n=== Raw LLM Output (first 300 chars) ===")
        print(data["rewrite"]["raw_llm_output"][:300])
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    main()
