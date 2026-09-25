from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ClauseAnalysis(BaseModel):
    id: str
    section_title: str
    original_text: str
    simplified_eli5: str
    simplified_practical: str
    simplified_business: str
    risk_level: str  # "critical", "warning", "info", "safe"
    risk_category: str  # "Liability", "Termination", "IP", "Payment", "Arbitration", "Auto-Renewal", etc.
    risk_explanation: str
    industry_standard: str
    recommended_counter_term: Optional[str] = None
    negotiation_leverage: str = "Medium"  # "High", "Medium", "Low"
    plain_english_score: str = "Grade 6 Readability"

class DocumentAnalysisResponse(BaseModel):
    document_id: str
    filename: str
    document_type: str  # "Lease", "NDA", "Employment", "Services Agreement", "Terms of Service", "General"
    overall_risk_score: int  # 0 to 100
    overall_risk_label: str  # "Low Risk", "Moderate Risk", "High Risk", "Critical Risk"
    executive_summary: str
    key_parties: List[str]
    governing_law: Optional[str] = None
    financial_commitments: List[str]
    clauses: List[ClauseAnalysis]
    red_flags_count: int
    warning_flags_count: int
    safe_flags_count: int
    category_counts: Dict[str, int] = {}
    readability_summary: str = "Grade 6 — Conversational English"
    deadlines_and_obligations: List[Dict[str, str]]
    presignature_checklist: List[Dict[str, Any]]
    attorney_questions: List[str]
    suggested_user_questions: List[str]
    ai_engine_used: str  # "Gemini 3.8 Flash" or "JurisClear Built-in Legal Intelligence Engine"

class AskQuestionRequest(BaseModel):
    document_id: Optional[str] = None
    document_text: str
    question: str
    api_key: Optional[str] = None

class AskQuestionResponse(BaseModel):
    question: str
    answer: str
    citations: List[Dict[str, str]]  # [{'clause_title': 'Section 4', 'quote': '...', 'page_or_para': 'Para 3'}]
    confidence: str
    practical_takeaway: str
    disclaimer: str

class CompareDocumentsRequest(BaseModel):
    doc_a_name: str
    doc_a_text: str
    doc_b_name: str
    doc_b_text: str
    api_key: Optional[str] = None

class DiffItem(BaseModel):
    category: str
    change_type: str  # "added", "removed", "modified", "unchanged"
    summary: str
    impact: str  # "More favorable to You", "More favorable to Counterparty", "Neutral"
    doc_a_excerpt: Optional[str] = None
    doc_b_excerpt: Optional[str] = None

class CompareDocumentsResponse(BaseModel):
    comparison_summary: str
    favorability_shift: str  # e.g. "Shifted 40% towards Counterparty"
    risk_delta: str  # "Significantly Higher Risk in Document B"
    key_differences: List[DiffItem]
    recommendation: str
    ai_engine_used: str

class GenerateCounterEmailRequest(BaseModel):
    document_id: Optional[str] = None
    recipient_role: str  # "Landlord", "Hiring Manager", "Client", "Vendor"
    clauses_to_negotiate: List[str]
    tone: str  # "Collaborative & Friendly", "Professional & Direct", "Firm"
    api_key: Optional[str] = None

class GenerateCounterEmailResponse(BaseModel):
    subject: str
    email_body: str
    talking_points: List[str]

class AttorneyBriefResponse(BaseModel):
    brief_markdown: str
    consultation_checklist: List[str]
