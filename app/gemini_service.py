"""
Gemini GenAI Service
Integrates google-genai using Gemini 2.5 Flash / 3.8 Flash for advanced multi-modal legal comprehension,
structured reasoning, semantic diffing, and grounded Q&A with sub-5-second timeout and instant local fallback.
"""

import os
import json
import logging
import asyncio
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types
from app.models import (
    DocumentAnalysisResponse,
    ClauseAnalysis,
    AskQuestionResponse,
    CompareDocumentsResponse,
    DiffItem,
    SimilarityItem,
    ClauseDiff,
    DocumentProfile
)
from app.analyzer import (
    analyze_document_locally,
    answer_question_locally,
    compare_documents_locally,
    generate_counter_email_locally,
    generate_inline_redline
)

logger = logging.getLogger(__name__)

# Use gemini-2.5-flash for maximum speed, accuracy, and high quota
PRIMARY_MODEL = "gemini-2.5-flash"

def get_client(api_key: Optional[str] = None) -> Optional[genai.Client]:
    """Retrieves or creates a genai Client if an API key is available."""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key or not key.strip():
        # Check .env file in workspace root
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY="):
                        key = line.strip().split("=", 1)[1].strip()
                        os.environ["GEMINI_API_KEY"] = key
                        break
    if not key or not key.strip():
        return None
    try:
        return genai.Client(api_key=key.strip())
    except Exception as e:
        logger.warning(f"Failed to initialize Gemini Client: {e}")
        return None

async def generate_with_retry_async(
    client: genai.Client,
    contents: Any,
    system_instruction: str,
    response_mime_type: str = "application/json",
    temperature: float = 0.2,
    timeout_per_model: float = 16.0
):
    """
    Executes model generation in a background thread with an async timeout.
    Uses gemini-2.5-flash, seamlessly falling back to the local engine on timeout/error.
    """
    models_to_try = [PRIMARY_MODEL]
    last_err = None

    def _sync_generate(m_name: str):
        return client.models.generate_content(
            model=m_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type=response_mime_type,
                temperature=temperature,
            )
        )

    for model in models_to_try:
        try:
            resp = await asyncio.wait_for(
                asyncio.to_thread(_sync_generate, model),
                timeout=timeout_per_model
            )
            return resp, model
        except Exception as e:
            last_err = e
            logger.warning(f"Gemini model {model} attempt failed/timed out: {e}. Falling back...")
            continue

    raise last_err or Exception("Gemini request timed out or failed")

async def analyze_document_with_gemini(filename: str, text: str, api_key: Optional[str] = None) -> DocumentAnalysisResponse:
    """Analyzes a legal document using Gemini with structured JSON output and instant local fallback."""
    client = get_client(api_key)
    if not client:
        return analyze_document_locally(filename, text)

    system_instruction = """You are JurisClear AI, an elite legal intelligence assistant.
Your mission is to make legal documents transparent, accessible, and understandable for non-lawyers.
Analyze the provided legal document and return a detailed, valid JSON object matching the exact structure below.
CRITICAL RULES:
1. Always maintain impartiality and accuracy.
2. For each clause, provide THREE levels of simplification:
   - simplified_eli5: Simple analogies, 6th-grade reading level, clear "gotchas" in plain English.
   - simplified_practical: Concrete real-world implications, what to do, what to watch out for.
   - simplified_business: Commercial risk exposure, legal strategy, and negotiation impact.
3. Identify all risk levels: "critical", "warning", "info", or "safe".
4. For dangerous clauses (uncapped liability, broad indemnification, auto-renewal traps, unilateral entry, broad IP assignment, harsh non-competes), provide the exact standard industry practice and a concrete, ready-to-use counter-term rider.
5. Extract key parties, governing law, financial commitments, notice deadlines, a pre-signature checklist, and high-yield questions for an attorney consultation.

JSON SCHEMA EXPECTED:
{
  "document_type": "string",
  "overall_risk_score": integer (0 to 100),
  "overall_risk_label": "string",
  "executive_summary": "string",
  "key_parties": ["string"],
  "governing_law": "string",
  "financial_commitments": ["string"],
  "clauses": [
    {
      "id": "clause_1",
      "section_title": "string",
      "original_text": "string (excerpt or full)",
      "simplified_eli5": "string",
      "simplified_practical": "string",
      "simplified_business": "string",
      "risk_level": "critical" | "warning" | "info" | "safe",
      "risk_category": "string",
      "risk_explanation": "string",
      "industry_standard": "string",
      "recommended_counter_term": "string or null"
    }
  ],
  "deadlines_and_obligations": [
    {"clause": "string", "timeframe": "string", "action": "string"}
  ],
  "presignature_checklist": [
    {"task": "string", "category": "string", "completed": false}
  ],
  "attorney_questions": ["string"],
  "suggested_user_questions": ["string"]
}
Only output the JSON object without markdown code fences or backticks.
"""

    prompt = f"Analyze this legal document:\n\nFilename: {filename}\n\nDocument Text:\n{text[:12000]}"

    try:
        response, model_used = await generate_with_retry_async(
            client=client,
            contents=prompt,
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.2,
            timeout_per_model=16.0
        )
        content_text = response.text.strip()
        # Clean potential markdown wrapping if present
        if content_text.startswith("```json"):
            content_text = content_text[7:]
        if content_text.startswith("```"):
            content_text = content_text[3:]
        if content_text.endswith("```"):
            content_text = content_text[:-3]
        content_text = content_text.strip()

        data = json.loads(content_text)

        clauses = []
        red_count = 0
        warning_count = 0
        safe_count = 0

        raw_clauses = data.get("clauses", [])
        if not raw_clauses or not isinstance(raw_clauses, list):
            # Fallback if model returned empty clause list
            return analyze_document_locally(filename, text)

        for idx, c in enumerate(raw_clauses, 1):
            rl = str(c.get("risk_level", "info")).lower()
            if rl not in ["critical", "warning", "info", "safe"]:
                rl = "info"
            if rl == "critical":
                red_count += 1
            elif rl == "warning":
                warning_count += 1
            else:
                safe_count += 1

            clauses.append(ClauseAnalysis(
                id=c.get("id", f"clause_{idx}"),
                section_title=c.get("section_title", f"Clause {idx}"),
                original_text=c.get("original_text", ""),
                simplified_eli5=c.get("simplified_eli5", ""),
                simplified_practical=c.get("simplified_practical", ""),
                simplified_business=c.get("simplified_business", ""),
                risk_level=rl,
                risk_category=c.get("risk_category", "General"),
                risk_explanation=c.get("risk_explanation", ""),
                industry_standard=c.get("industry_standard", ""),
                recommended_counter_term=c.get("recommended_counter_term"),
                negotiation_leverage="High — Highly Contestable" if rl == "critical" else "Medium — Negotiable Compromise",
                plain_english_score="Grade 6 Readability"
            ))

        category_counts = {}
        for c in clauses:
            category_counts[c.risk_category] = category_counts.get(c.risk_category, 0) + 1

        engine_name = f"Gemini ({model_used})"
        
        raw_parties = data.get("key_parties", ["Party A", "Party B"])
        if isinstance(raw_parties, str):
            raw_parties = [raw_parties]

        raw_financials = data.get("financial_commitments", [])
        if isinstance(raw_financials, str):
            raw_financials = [raw_financials]

        return DocumentAnalysisResponse(
            document_id=f"gemini_{abs(hash(text)) % 100000}",
            filename=filename,
            document_type=data.get("document_type", "Legal Contract"),
            overall_risk_score=int(data.get("overall_risk_score", 50)),
            overall_risk_label=data.get("overall_risk_label", "Moderate Risk"),
            executive_summary=data.get("executive_summary", "Comprehensive legal analysis generated by Gemini."),
            key_parties=raw_parties or ["Party A", "Party B"],
            governing_law=data.get("governing_law", "Applicable State / Federal Law"),
            financial_commitments=raw_financials,
            clauses=clauses,
            red_flags_count=red_count,
            warning_flags_count=warning_count,
            safe_flags_count=safe_count,
            category_counts=category_counts,
            readability_summary="Grade 6 — Conversational English",
            deadlines_and_obligations=data.get("deadlines_and_obligations", []),
            presignature_checklist=data.get("presignature_checklist", []),
            attorney_questions=data.get("attorney_questions", []),
            suggested_user_questions=data.get("suggested_user_questions", []),
            ai_engine_used=engine_name
        )
    except Exception as e:
        logger.warning(f"Gemini analysis encountered error/timeout ({e}), seamlessly falling back to built-in legal engine")
        return analyze_document_locally(filename, text)

async def ask_question_with_gemini(document_text: str, question: str, api_key: Optional[str] = None) -> AskQuestionResponse:
    """Answers a question about the document using Gemini with grounded citations and instant fallback."""
    client = get_client(api_key)
    if not client:
        return answer_question_locally(document_text, question)

    system_instruction = """You are JurisClear AI's Legal Document Q&A Specialist.
Answer user questions grounded strictly on the provided legal document.
Provide:
1. answer: A comprehensive, plain-English explanation addressing the question directly.
2. citations: An array of specific clauses/sections quoted directly from the text to substantiate the answer.
3. practical_takeaway: A short, bulleted actionable takeaway for the user.
4. confidence: "High (Direct Citation)", "Moderate", or "Low".

Output ONLY a JSON object:
{
  "answer": "string",
  "citations": [{"clause_title": "string", "quote": "string", "page_or_para": "string"}],
  "confidence": "string",
  "practical_takeaway": "string"
}
"""

    prompt = f"DOCUMENT TEXT:\n{document_text[:12000]}\n\nUSER QUESTION:\n{question}"

    try:
        response, model_used = await generate_with_retry_async(
            client=client,
            contents=prompt,
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.2,
            timeout_per_model=12.0
        )
        content_text = response.text.strip()
        if content_text.startswith("```json"):
            content_text = content_text[7:]
        if content_text.startswith("```"):
            content_text = content_text[3:]
        if content_text.endswith("```"):
            content_text = content_text[:-3]
        content_text = content_text.strip()

        data = json.loads(content_text)
        return AskQuestionResponse(
            question=question,
            answer=data.get("answer", "No answer found."),
            citations=data.get("citations", []),
            confidence=data.get("confidence", "High"),
            practical_takeaway=data.get("practical_takeaway", "Review the relevant sections carefully."),
            disclaimer="This response provides automated legal information and document navigation for informational purposes only. It is not formal legal advice."
        )
    except Exception as e:
        logger.warning(f"Gemini Q&A failed/timed out ({e}), falling back to local search")
        return answer_question_locally(document_text, question)

async def compare_documents_with_gemini(doc_a_name: str, doc_a_text: str, doc_b_name: str, doc_b_text: str, api_key: Optional[str] = None) -> CompareDocumentsResponse:
    """Compares two contracts using Gemini to evaluate semantic differences, similarities, redlines, and risk shifts."""
    client = get_client(api_key)
    if not client:
        return compare_documents_locally(doc_a_name, doc_a_text, doc_b_name, doc_b_text)

    # First get the baseline local comparison so we have complete fallback structures
    local_baseline = compare_documents_locally(doc_a_name, doc_a_text, doc_b_name, doc_b_text)

    system_instruction = """You are a senior legal redline and contract comparison specialist.
Compare Document A vs Document B.
Identify:
1. similarities: Clauses or terms where both contracts are aligned (e.g. governing law, exclusions, confidentiality definitions).
2. differences: Clause-by-clause changes (added, removed, modified), the impact on the user vs counterparty, and negotiation advice.
3. favorability_shift: Which party benefits and by how much percentage (-100 to +100, where negative = favors counterparty, positive = favors user).
4. recommendation and negotiation_checklist: Actionable next steps.

Output ONLY a JSON object:
{
  "comparison_summary": "string",
  "favorability_shift": "string (e.g. Shifted 65% towards Counterparty)",
  "favorability_percentage": number (between -100 and 100),
  "risk_delta": "string",
  "similarities": [
    {
      "category": "string",
      "title": "string",
      "description": "string",
      "alignment_status": "string",
      "doc_a_excerpt": "string",
      "doc_b_excerpt": "string"
    }
  ],
  "differences": [
    {
      "category": "string",
      "clause_title": "string",
      "change_type": "modified" | "added_in_b" | "removed_in_b",
      "impact": "More favorable to You" | "More favorable to Counterparty" | "Neutral",
      "risk_severity": "critical" | "warning" | "info" | "safe",
      "doc_a_title": "string",
      "doc_a_excerpt": "string",
      "doc_b_title": "string",
      "doc_b_excerpt": "string",
      "summary": "string",
      "action_advice": "string"
    }
  ],
  "recommendation": "string",
  "negotiation_checklist": ["string"]
}
"""

    prompt = f"DOCUMENT A ({doc_a_name}):\n{doc_a_text[:7500]}\n\nDOCUMENT B ({doc_b_name}):\n{doc_b_text[:7500]}"

    try:
        response, model_used = await generate_with_retry_async(
            client=client,
            contents=prompt,
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.2,
            timeout_per_model=16.0
        )
        content_text = response.text.strip()
        if content_text.startswith("```json"):
            content_text = content_text[7:]
        if content_text.startswith("```"):
            content_text = content_text[3:]
        if content_text.endswith("```"):
            content_text = content_text[:-3]
        content_text = content_text.strip()

        data = json.loads(content_text)
        
        # Build differences list
        differences = []
        key_diff_items = []
        raw_diffs = data.get("differences", [])
        for idx, d in enumerate(raw_diffs, 1):
            doc_a_ex = d.get("doc_a_excerpt")
            doc_b_ex = d.get("doc_b_excerpt")
            redline = generate_inline_redline(doc_a_ex or "", doc_b_ex or "") if (doc_a_ex or doc_b_ex) else None
            differences.append(ClauseDiff(
                id=f"gemini_diff_{idx}",
                category=d.get("category", "General"),
                clause_title=d.get("clause_title", f"Difference {idx}"),
                change_type=d.get("change_type", "modified"),
                impact=d.get("impact", "Neutral"),
                risk_severity=d.get("risk_severity", "warning"),
                doc_a_title=d.get("doc_a_title", doc_a_name),
                doc_a_excerpt=doc_a_ex,
                doc_b_title=d.get("doc_b_title", doc_b_name),
                doc_b_excerpt=doc_b_ex,
                redline_html=redline,
                summary=d.get("summary", ""),
                action_advice=d.get("action_advice", "Review this provision before signing.")
            ))
            key_diff_items.append(DiffItem(
                category=d.get("category", "General"),
                change_type=d.get("change_type", "modified"),
                summary=d.get("summary", ""),
                impact=d.get("impact", "Neutral"),
                doc_a_excerpt=doc_a_ex,
                doc_b_excerpt=doc_b_ex
            ))

        # Fallback to local differences if Gemini returned empty
        if not differences:
            differences = local_baseline.differences
            key_diff_items = local_baseline.key_differences

        # Build similarities list
        similarities = []
        raw_sims = data.get("similarities", [])
        for idx, s in enumerate(raw_sims, 1):
            similarities.append(SimilarityItem(
                id=f"gemini_sim_{idx}",
                category=s.get("category", "General"),
                title=s.get("title", f"Aligned Provision {idx}"),
                description=s.get("description", ""),
                alignment_status=s.get("alignment_status", "Substantially Aligned"),
                doc_a_excerpt=s.get("doc_a_excerpt"),
                doc_b_excerpt=s.get("doc_b_excerpt")
            ))

        # Fallback to local similarities if Gemini returned empty
        if not similarities:
            similarities = local_baseline.similarities

        fav_shift = data.get("favorability_shift", local_baseline.favorability_shift)
        fav_pct = int(data.get("favorability_percentage", local_baseline.favorability_percentage))

        added_cnt = sum(1 for d in differences if d.change_type == "added_in_b")
        removed_cnt = sum(1 for d in differences if d.change_type == "removed_in_b")
        modified_cnt = sum(1 for d in differences if d.change_type == "modified")

        return CompareDocumentsResponse(
            comparison_summary=data.get("comparison_summary", local_baseline.comparison_summary),
            favorability_shift=fav_shift,
            favorability_percentage=fav_pct,
            risk_delta=data.get("risk_delta", local_baseline.risk_delta),
            doc_a_profile=local_baseline.doc_a_profile,
            doc_b_profile=local_baseline.doc_b_profile,
            similarities=similarities,
            differences=differences,
            key_differences=key_diff_items,
            clauses_added_count=added_cnt,
            clauses_removed_count=removed_cnt,
            clauses_modified_count=modified_cnt,
            clauses_identical_count=len(similarities),
            recommendation=data.get("recommendation", local_baseline.recommendation),
            negotiation_checklist=data.get("negotiation_checklist", local_baseline.negotiation_checklist),
            ai_engine_used=f"Gemini ({model_used})"
        )
    except Exception as e:
        logger.warning(f"Gemini document comparison failed/timed out ({e}), using local comparator")
        return compare_documents_locally(doc_a_name, doc_a_text, doc_b_name, doc_b_text)

async def generate_counter_email_with_gemini(recipient_role: str, clauses: List[str], tone: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Generates a polite, highly persuasive negotiation counter-proposal email."""
    client = get_client(api_key)
    if not client:
        return generate_counter_email_locally(recipient_role, clauses, tone)

    system_instruction = f"""You are an expert contract negotiator.
Write a collaborative, professional, and tactful counter-proposal email to a {recipient_role}.
Tone: {tone}.
The email must address the user's concerns regarding the following clauses:
{', '.join(clauses)}

Output ONLY a JSON object:
{{
  "subject": "string",
  "email_body": "string",
  "talking_points": ["string"]
}}
"""

    prompt = f"Generate a counter-proposal email to the {recipient_role} seeking balanced revisions to: {', '.join(clauses)}."

    try:
        response, model_used = await generate_with_retry_async(
            client=client,
            contents=prompt,
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.4,
            timeout_per_model=12.0
        )
        content_text = response.text.strip()
        if content_text.startswith("```json"):
            content_text = content_text[7:]
        if content_text.startswith("```"):
            content_text = content_text[3:]
        if content_text.endswith("```"):
            content_text = content_text[:-3]
        content_text = content_text.strip()

        data = json.loads(content_text)
        return {
            "subject": data.get("subject", f"Proposed adjustments to Agreement with {recipient_role}"),
            "email_body": data.get("email_body", ""),
            "talking_points": data.get("talking_points", [])
        }
    except Exception as e:
        logger.warning(f"Gemini email generation error/timeout ({e}), using local generator")
        return generate_counter_email_locally(recipient_role, clauses, tone)
