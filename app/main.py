"""
JurisClear AI — FastAPI Application Server
Provides RESTful APIs for legal document simplification, risk radar,
contract comparison, grounded Q&A, and attorney consultation prep.
"""

import os
import io
import pypdf
import docx
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.models import (
    DocumentAnalysisResponse,
    AskQuestionRequest,
    AskQuestionResponse,
    CompareDocumentsRequest,
    CompareDocumentsResponse,
    GenerateCounterEmailRequest,
    GenerateCounterEmailResponse,
    AttorneyBriefResponse
)
from app.sample_contracts import SAMPLE_CONTRACTS
from app.gemini_service import (
    analyze_document_with_gemini,
    ask_question_with_gemini,
    compare_documents_with_gemini,
    generate_counter_email_with_gemini
)

app = FastAPI(
    title="JurisClear AI — GenAI Legal Accessibility Platform",
    description="Makes legal contracts transparent, understandable, and negotiable for everyday people.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# In-memory document storage for the session
DOCUMENT_STORE = {}

class AnalyzeTextRequest(BaseModel):
    title: str
    text: str
    api_key: Optional[str] = None

@app.get("/api/health")
async def health_check():
    has_env_key = bool(os.environ.get("GEMINI_API_KEY"))
    if not has_env_key:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY="):
                        val = line.strip().split("=", 1)[1].strip()
                        if val:
                            os.environ["GEMINI_API_KEY"] = val
                            has_env_key = True
                            break
    return {
        "status": "healthy",
        "app_name": "JurisClear AI",
        "version": "1.0.0",
        "gemini_env_key_configured": has_env_key,
        "default_engine": "Gemini 2.5 Flash (Active)" if has_env_key else "JurisClear Built-in Legal Engine (Ready) + Gemini Compatible"
    }

@app.get("/api/samples")
async def list_sample_contracts():
    """Lists available realistic legal document samples for instant test drives."""
    return [
        {
            "id": key,
            "title": data["title"],
            "type": data["type"],
            "description": data["description"]
        }
        for key, data in SAMPLE_CONTRACTS.items()
    ]

@app.get("/api/samples/{sample_id}")
async def get_sample_contract(sample_id: str):
    """Retrieves full text and metadata for a selected sample contract."""
    if sample_id not in SAMPLE_CONTRACTS:
        raise HTTPException(status_code=404, detail="Sample contract not found.")
    return SAMPLE_CONTRACTS[sample_id]

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB limit
MAX_TEXT_LENGTH = 300000  # 300k chars limit

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """Uploads and parses a PDF, DOCX, or TXT legal contract."""
    filename = file.filename or "uploaded_document.txt"
    ext = filename.lower().split(".")[-1]
    contents = await file.read()
    
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large ({len(contents) / (1024*1024):.1f}MB). Maximum allowed size is 15MB.")

    extracted_text = ""

    try:
        if ext == "pdf":
            reader = pypdf.PdfReader(io.BytesIO(contents))
            pages_text = []
            for page_num, page in enumerate(reader.pages, 1):
                page_content = page.extract_text() or ""
                if page_content.strip():
                    pages_text.append(f"--- PAGE {page_num} ---\n{page_content}")
            extracted_text = "\n\n".join(pages_text)
            if not extracted_text.strip():
                raise HTTPException(status_code=400, detail="Could not extract readable text from PDF. The document may be scanned images.")
        elif ext in ["docx", "doc"]:
            doc = docx.Document(io.BytesIO(contents))
            extracted_text = "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        elif ext in ["txt", "md"]:
            extracted_text = contents.decode("utf-8", errors="replace")
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format '.{ext}'. Please upload a PDF, DOCX, or TXT file.")

        doc_id = f"doc_{abs(hash(extracted_text)) % 100000}"
        DOCUMENT_STORE[doc_id] = {
            "filename": filename,
            "text": extracted_text
        }

        return {
            "document_id": doc_id,
            "filename": filename,
            "character_count": len(extracted_text),
            "word_count": len(extracted_text.split()),
            "text_preview": extracted_text[:500] + ("..." if len(extracted_text) > 500 else "")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing document: {str(e)}")

@app.post("/api/analyze", response_model=DocumentAnalysisResponse)
async def analyze_document(request: AnalyzeTextRequest):
    """Performs comprehensive legal analysis, risk radar scoring, and multi-tier simplification."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Document text cannot be empty.")
    
    if len(request.text) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=413, detail=f"Document text exceeds {MAX_TEXT_LENGTH:,} character limit.")

    analysis = await analyze_document_with_gemini(
        filename=request.title,
        text=request.text,
        api_key=request.api_key
    )
    # Store for follow-up Q&A
    DOCUMENT_STORE[analysis.document_id] = {
        "filename": request.title,
        "text": request.text,
        "analysis": analysis
    }
    return analysis

@app.post("/api/ask", response_model=AskQuestionResponse)
async def ask_question(request: AskQuestionRequest):
    """Answers user question about a legal document with specific citations and practical advice."""
    doc_text = request.document_text
    if not doc_text and request.document_id and request.document_id in DOCUMENT_STORE:
        doc_text = DOCUMENT_STORE[request.document_id]["text"]

    if not doc_text or not doc_text.strip():
        raise HTTPException(status_code=400, detail="Document text is required to answer questions.")

    return await ask_question_with_gemini(
        document_text=doc_text,
        question=request.question,
        api_key=request.api_key
    )

@app.post("/api/compare", response_model=CompareDocumentsResponse)
async def compare_documents(request: CompareDocumentsRequest):
    """Compares two contracts (e.g. Standard vs Custom, v1 vs v2) and outputs redline & risk delta."""
    if not request.doc_a_text.strip() or not request.doc_b_text.strip():
        raise HTTPException(status_code=400, detail="Both Document A and Document B text are required for comparison.")

    return await compare_documents_with_gemini(
        doc_a_name=request.doc_a_name,
        doc_a_text=request.doc_a_text,
        doc_b_name=request.doc_b_name,
        doc_b_text=request.doc_b_text,
        api_key=request.api_key
    )

@app.post("/api/generate-email", response_model=GenerateCounterEmailResponse)
async def generate_counter_email(request: GenerateCounterEmailRequest):
    """Generates a professional counter-proposal negotiation email."""
    if not request.clauses_to_negotiate:
        raise HTTPException(status_code=400, detail="Please select at least one clause to negotiate.")

    result = await generate_counter_email_with_gemini(
        recipient_role=request.recipient_role,
        clauses=request.clauses_to_negotiate,
        tone=request.tone,
        api_key=request.api_key
    )
    return GenerateCounterEmailResponse(
        subject=result["subject"],
        email_body=result["email_body"],
        talking_points=result["talking_points"]
    )

@app.post("/api/attorney-brief", response_model=AttorneyBriefResponse)
async def generate_attorney_brief(analysis: DocumentAnalysisResponse):
    """Generates an executive legal consultation briefing dossier formatted to save lawyer billable hours."""
    critical_clauses = [c for c in analysis.clauses if c.risk_level == "critical"]
    warning_clauses = [c for c in analysis.clauses if c.risk_level == "warning"]

    brief = []
    brief.append(f"# ATTORNEY CONSULTATION BRIEFING DOSSIER")
    brief.append(f"**Document Name:** {analysis.filename}")
    brief.append(f"**Document Type:** {analysis.document_type}")
    brief.append(f"**Overall Assessed Risk:** {analysis.overall_risk_label} (Score: {analysis.overall_risk_score}/100)")
    brief.append(f"**Governing Law:** {analysis.governing_law}")
    brief.append(f"**Identified Contracting Parties:** {', '.join(analysis.key_parties)}")
    brief.append("\n---\n")

    brief.append("## 1. Executive Summary & Purpose")
    brief.append(analysis.executive_summary)
    brief.append("\n")

    brief.append("## 2. Critical Legal Red Flags (Action Required)")
    if critical_clauses:
        for idx, c in enumerate(critical_clauses, 1):
            brief.append(f"### {idx}. {c.section_title} [{c.risk_category}]")
            brief.append(f"- **Specific Exposure:** {c.risk_explanation}")
            brief.append(f"- **Relevant Text Excerpt:** *\"{c.original_text[:280]}...\"*")
            brief.append(f"- **Commercial Standard:** {c.industry_standard}")
            if c.recommended_counter_term:
                brief.append(f"- **Proposed Redline Substitute:** `{c.recommended_counter_term}`")
            brief.append("\n")
    else:
        brief.append("No critical red flags detected. Proceed with standard clause diligence.\n")

    brief.append("## 3. High-Priority Questions for Legal Counsel")
    brief.append("*Bring these specific questions to maximize your consultation efficiency and save billable hours:*")
    for idx, q in enumerate(analysis.attorney_questions, 1):
        brief.append(f"{idx}. {q}")
    brief.append("\n")

    brief.append("## 4. Key Deadlines, Notices & Milestones")
    for d in analysis.deadlines_and_obligations:
        brief.append(f"- **{d.get('timeframe', 'Notice Window')}:** {d.get('action', 'Compliance action')}")
    brief.append("\n")

    brief.append("---\n")
    brief.append("*DISCLAIMER: This briefing dossier was prepared with JurisClear AI to organize facts and flag terms for attorney review. It does not constitute formal legal advice or create an attorney-client relationship.*")

    checklist = [
        "Bring this briefing document and full marked contract to consultation.",
        "Clarify which clauses are non-negotiable standard policy versus customizable.",
        "Request counsel's preferred limitation of liability rider text.",
        "Confirm statutory cooling-off or habitability rights under local law.",
        "Establish counsel's fee estimate if formal redline markup is required."
    ]

    return AttorneyBriefResponse(
        brief_markdown="\n".join(brief),
        consultation_checklist=checklist
    )

# Mount static directory for frontend
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"})
    return JSONResponse({"message": "JurisClear AI API is running. Static files loading..."})
