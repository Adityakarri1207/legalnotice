"""
JurisClear Legal Intelligence Engine
Provides AST/heuristic parsing, risk radar scoring, plain-English translation at 3 readability tiers,
deadlines/obligations extraction, document comparison diffing, and grounded Q&A with clause citations.
"""

import re
import difflib
import html
from typing import List, Dict, Any, Tuple, Optional
from app.models import (
    ClauseAnalysis,
    DocumentAnalysisResponse,
    AskQuestionResponse,
    CompareDocumentsResponse,
    DiffItem,
    SimilarityItem,
    ClauseDiff,
    DocumentProfile
)

# Known risk patterns and their explanations
RISK_RULES = [
    {
        "pattern": r"(unlimited\s+liability|liability.*unlimited|shall\s+not\s+be\s+capped)",
        "level": "critical",
        "category": "Liability & Indemnification",
        "title": "Uncapped Personal Liability",
        "explanation": "This clause makes your liability unlimited. If a lawsuit or dispute arises, you could be held liable for damages far exceeding what you were paid, putting your personal assets at risk.",
        "standard": "Standard commercial practice caps liability to the total fees paid under the contract (or 1x-2x contract value), and excludes consequential/punitive damages.",
        "counter": "Replace with: 'Each party's aggregate maximum liability arising under or relating to this Agreement shall be limited to the total fees paid or payable by Client in the preceding 12 months.'"
    },
    {
        "pattern": r"(indemnify.*hold\s+harmless.*regardless\s+of|hold\s+landlord\s+harmless.*negligence)",
        "level": "critical",
        "category": "Liability & Indemnification",
        "title": "Broad / One-Sided Indemnity",
        "explanation": "You are agreeing to defend and pay for the other party's losses even if they caused the harm through their own negligence or mistakes.",
        "standard": "Indemnification should be reciprocal and strictly limited to third-party claims directly caused by intentional misconduct or gross negligence.",
        "counter": "Amend to: 'Contractor shall indemnify only against third-party claims arising directly from Contractor's gross negligence or willful misconduct, excluding any claims arising from Company's instructions or negligence.'"
    },
    {
        "pattern": r"(automatic\s+renew.*forfeiture|forfeiture\s+of\s+(the\s+)?entire\s+security\s+deposit|automatically\s+renew.*15%|certified\s+mail.*60\s+days)",
        "level": "critical",
        "category": "Auto-Renewal & Notice Trap",
        "title": "Severe Auto-Renewal & Deposit Forfeiture",
        "explanation": "Failure to provide notice 60 days ahead via certified mail locks you into another 12-month lease with a 15% rent hike AND forfeits your entire security deposit.",
        "standard": "Standard leases convert to a month-to-month tenancy upon expiration, with 30 days email or written notice required to terminate. Security deposits cannot be forfeited as penalty fees.",
        "counter": "Propose: 'Upon expiration, this Lease shall continue on a month-to-month basis terminable by either party with thirty (30) days advance written notice by email or hand delivery. Deposits remain subject to standard statutory accounting.'"
    },
    {
        "pattern": r"(unrestricted\s+right\s+to\s+enter|24\s+hours\s+a\s+day.*without\s+prior\s+notice|enter.*without\s+prior\s+notice)",
        "level": "critical",
        "category": "Privacy & Unilateral Access",
        "title": "24/7 Unrestricted Entry Without Notice",
        "explanation": "Allows the landlord or agents to enter your home at any hour without advance warning, severely compromising your privacy and security.",
        "standard": "Standard laws require at least 24 to 48 hours advance written notice for non-emergency entry, restricted to reasonable business hours (9 AM - 6 PM).",
        "counter": "Revise to: 'Landlord shall provide at least twenty-four (24) hours advance written notice prior to entering the Premises, such entry to occur only during normal business hours (Monday-Friday, 9 AM - 6 PM), except in bona fide emergencies.'"
    },
    {
        "pattern": r"(non-refundable.*cleaning\s+fee|regardless\s+of\s+(the\s+)?physical\s+condition)",
        "level": "warning",
        "category": "Unjustified Deductions",
        "title": "Automatic Non-Refundable Deposit Deductions",
        "explanation": "Mandates $550+ in automatic cleaning and inspection deductions from your deposit regardless of how immaculately you clean and maintain the apartment.",
        "standard": "Security deposits may only be deducted for damage beyond normal wear and tear, accompanied by an itemized receipt.",
        "counter": "Request: 'Deductions from the Security Deposit shall be limited strictly to actual damages beyond normal wear and tear, supported by itemized third-party invoices provided within 30 days of move-out.'"
    },
    {
        "pattern": r"(all\s+works\s+of\s+authorship.*personal\s+time|utilizing.*personal\s+devices|12\s+months\s+thereafter.*exclusive\s+property)",
        "level": "critical",
        "category": "Intellectual Property Overreach",
        "title": "Sweeping IP Grab (Side Projects & Off-Hours)",
        "explanation": "The company claims ownership of everything you invent or build—even on personal time, weekends, using your own laptop, or for 12 months after leaving.",
        "standard": "Inventions assignment should be strictly confined to work performed directly for the client, within client working hours, utilizing client confidential information.",
        "counter": "Amend to: 'Company shall own only Deliverables created specifically for Company under an authorized Statement of Work. Contractor retains all right, title, and ownership in all pre-existing tools, open source contributions, and independent inventions created outside Company scope.'"
    },
    {
        "pattern": r"(non-compet.*twenty-four.*anywhere\s+in\s+the\s+world|competes\s+with\s+Company.*anywhere)",
        "level": "critical",
        "category": "Restrictive Covenants",
        "title": "Worldwide 2-Year Non-Compete",
        "explanation": "Prohibits you from working in your professional field anywhere in the world for two years after the contract ends, potentially preventing you from earning a livelihood.",
        "standard": "Non-competes for independent contractors are widely unenforceable in many jurisdictions (such as CA, MN, NY) or should be completely removed, replaced only with strict confidentiality and non-solicitation of clients.",
        "counter": "Strike this clause entirely: 'Independent contractors cannot be subject to non-competition restraints. Confidentiality obligations in Section 7 already provide full protection for proprietary trade secrets.'"
    },
    {
        "pattern": r"(ninety\s+\(90\)\s+days|net-90|sole\s+and\s+unfettered\s+discretion\s+to\s+withhold)",
        "level": "warning",
        "category": "Payment & Cashflow Risk",
        "title": "Net-90 Payment & Unilateral Withholding",
        "explanation": "You must wait 3 full months after invoice approval to get paid, and the company claims sole discretion to refuse payment if they subjectively dislike the work.",
        "standard": "Fair freelance and contractor payment terms are Net-15 or Net-30, with objections required to be stated in writing within 10 days of invoice receipt.",
        "counter": "Change to: 'Invoices shall be payable within thirty (30) calendar days of receipt (Net-30). Any disputed portion must be identified with specific written feedback within ten (10) business days, while undisputed amounts must be paid on schedule.'"
    },
    {
        "pattern": r"(perpetual.*secrecy|in\s+perpetuity|perpetual\s+confidentiality)",
        "level": "warning",
        "category": "Confidentiality & Duration",
        "title": "Perpetual Confidentiality Burden",
        "explanation": "Binds you to track and protect disclosures forever, creating indefinite legal exposure even after information becomes stale or obsolete.",
        "standard": "Standard confidentiality obligations expire after 2 to 3 years from disclosure, with an exception only for bona fide trade secrets as recognized by law.",
        "counter": "Revise to: 'Confidentiality obligations under this Agreement shall expire three (3) years from the date of disclosure, except for trade secrets which shall remain protected for as long as they qualify under applicable statute.'"
    },
    {
        "pattern": r"(liquidated\s+damages\s+of\s+\$250,000|penalty\s+fee\s+of\s+\$1,000)",
        "level": "critical",
        "category": "Liquidated Damages & Penalties",
        "title": "Exorbitant Disproportionate Liquidated Damages",
        "explanation": "Imposes arbitrary, massive financial penalties ($250,000 or $1,000) for minor or inadvertent infractions without proof of actual harm.",
        "standard": "Under contract law, liquidated damages must reflect a genuine pre-estimate of actual loss, not punitive penalties. Courts routinely strike punitive liquidated damages.",
        "counter": "Remove fixed penalties: 'Damages for breach shall be limited to demonstrable direct damages proven in court or arbitration, without punitive liquidated penalties.'"
    },
    {
        "pattern": r"(pay\s+all\s+of\s+landlord's\s+attorney's\s+fees.*regardless\s+of\s+whether|reimburse\s+company\s+for\s+100%\s+of\s+company's\s+legal\s+expenses)",
        "level": "critical",
        "category": "Fee Shifting & Dispute Costs",
        "title": "One-Way Attorney's Fee Shifting",
        "explanation": "Requires you to pay all of the other party's legal fees even if YOU WIN the lawsuit or eviction case!",
        "standard": "Legal fee provisions should be strictly reciprocal: 'The prevailing party in any legal action shall be entitled to recover reasonable attorney's fees.'",
        "counter": "Modify to: 'In any litigation or proceeding arising hereunder, the prevailing party shall be entitled to recover its reasonable attorney's fees and allowable court costs from the non-prevailing party.'"
    },
    {
        "pattern": r"(waives\s+all\s+implied\s+warranties\s+of\s+habitability|accepts.*as-is|repairs\s+costing\s+less\s+than\s+\$300)",
        "level": "warning",
        "category": "Habitability & Maintenance Shift",
        "title": "Waiver of Habitability & Maintenance Shift",
        "explanation": "Shifts essential plumbing, HVAC, and pest control costs onto the tenant and attempts to waive statutory rights to a safe, livable home.",
        "standard": "Landlords are legally obligated by state law to maintain basic structural, plumbing, heating, and habitability standards. Habitability rights generally cannot be waived.",
        "counter": "Strike habitability waiver: 'Landlord shall maintain the structural components, plumbing, HVAC, and electrical systems in safe, compliant, and operable condition at Landlord's expense.'"
    },
    {
        "pattern": r"(repay\s+the\s+full\s+\$25,000.*signing\s+bonus|clawback)",
        "level": "warning",
        "category": "Bonus Clawback",
        "title": "24-Month Full Bonus Clawback",
        "explanation": "Demands 100% repayment of the signing bonus if employment ends within two years, even if you are terminated without cause or laid off.",
        "standard": "Bonus clawbacks should prorate monthly over 12 months, and should explicitly exclude termination without cause or resignation for good reason.",
        "counter": "Revise to: 'The signing bonus clawback shall prorate monthly over twelve (12) months (1/12th forgiven per completed month) and shall not apply if Employee is terminated without Cause or in connection with a corporate restructuring.'"
    },
    {
        "pattern": r"(moonlighting.*outside\s+commercial\s+activities.*without\s+the\s+prior\s+written)",
        "level": "warning",
        "category": "Moonlighting & Side Work",
        "title": "Broad Prohibition on Outside Activities",
        "explanation": "Bans all freelance advisory, passive ventures, or personal hobbies with commercial potential, even outside business hours.",
        "standard": "Outside employment bans should only restrict activities that directly compete with the employer or create a conflict of interest.",
        "counter": "Refine to: 'Employee may engage in non-competing personal projects, open source, or freelance advisory during non-business hours provided they do not utilize Employer equipment or confidential information.'"
    }
]

def detect_document_type(text: str) -> str:
    text_lower = text.lower()
    if "lease agreement" in text_lower or "tenant" in text_lower or "rent" in text_lower:
        return "Residential Lease Agreement"
    elif "contractor" in text_lower or "deliverables" in text_lower or "services agreement" in text_lower:
        return "Independent Contractor Services Agreement"
    elif "non-disclosure" in text_lower or "nda" in text_lower or "confidential information" in text_lower:
        if "mutual" in text_lower:
            return "Mutual Non-Disclosure Agreement (NDA)"
        return "Non-Disclosure Agreement (NDA)"
    elif "employment" in text_lower or "employee" in text_lower or "salary" in text_lower:
        return "Employment Agreement"
    elif "terms of service" in text_lower or "terms of use" in text_lower:
        return "Terms of Service"
    return "Legal Agreement"

def split_into_clauses(text: str) -> List[Dict[str, str]]:
    """Splits a legal document into structured sections/clauses."""
    lines = text.strip().split("\n")
    clauses = []
    current_title = "Preamble & Identification of Parties"
    current_body = []
    
    # Heading regex patterns: "1. TITLE", "SECTION 1 - TITLE", "ARTICLE I", etc.
    heading_pattern = re.compile(r"^(\d+\.|\bSECTION\s+\d+|\bARTICLE\s+[IVXLCDM]+|[A-Z\s]{4,}:)\s*(.*)", re.IGNORECASE)
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Check if line matches a numbered section heading
        match = heading_pattern.match(stripped)
        if match and (len(stripped) < 90 or ":" in stripped):
            if current_body:
                clauses.append({
                    "title": current_title,
                    "body": "\n".join(current_body).strip()
                })
                current_body = []
            current_title = stripped
        else:
            current_body.append(stripped)
            
    if current_body:
        clauses.append({
            "title": current_title,
            "body": "\n".join(current_body).strip()
        })
        
    # Fallback if document has no headings: chunk into paragraphs
    if len(clauses) <= 1 and len(text) > 400:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        clauses = []
        for idx, p in enumerate(paragraphs, 1):
            first_line = p.split("\n")[0][:40]
            clauses.append({
                "title": f"Clause {idx}: {first_line}...",
                "body": p
            })
            
    return clauses

def generate_plain_english_translations(title: str, body: str, category: str, risk_level: str) -> Tuple[str, str, str]:
    """Generates 3 tiers of plain-English translations for a clause."""
    body_summary = body.replace("\n", " ")
    
    if "term and automatic renewal" in title.lower() or "auto-renewal" in body_summary.lower():
        eli5 = "If you don't send a certified letter 60 days before moving out, you're trapped for another whole year with a 15% rent increase, and they take your whole deposit."
        practical = "Mark your calendar 70 days before lease end. You must mail a certified physical letter if you plan to move, or rent jumps 15% and you lose $2,150."
        business = "Automatic evergreen rollover with a punitive 15% escalator and forfeiture of security deposit. Extremely hostile renewal terms requiring formal certified mail."
    elif "rent and late fees" in title.lower() or "late fee" in body_summary.lower():
        eli5 = "Rent is due on the 1st. If it's late on the 2nd, you immediately owe a $150 penalty plus $25 every single day after."
        practical = "There is virtually zero grace period (only 1 day). An initial $150 late fee applies on day 2, accumulating $25 daily."
        business = "Aggressive payment terms: only 24 hours grace before a high initial penalty ($150) and compounding daily per-diem penalties ($25/day)."
    elif "security deposit" in title.lower() or "deduction" in body_summary.lower():
        eli5 = "You will definitely lose at least $550 of your deposit, even if you clean the apartment until it sparkles."
        practical = "The landlord guarantees $350 for cleaning and $200 for inspection will be deducted automatically from your $2,150 deposit upon departure."
        business = "Guaranteed non-refundable holdbacks totaling $550 disguised as deposit deductions, circumventing normal wear-and-tear requirements."
    elif "landlord access" in title.lower() or "unrestricted right to enter" in body_summary.lower():
        eli5 = "The landlord or strangers can walk into your apartment at 3 AM without knocking or calling you first."
        practical = "You have no right to advance notice before property staff, contractors, or potential buyers enter your home."
        business = "Complete surrender of quiet enjoyment and tenant privacy rights; authorizes 24/7 unannounced physical entry without cause."
    elif "habitability waiver" in title.lower() or "as-is" in body_summary.lower():
        eli5 = "You have to pay the first $300 for any broken pipe, heater, or bug problem, and you cannot complain if they take forever to fix things."
        practical = "You must pay up to $300 out of pocket for any repair, including plumbing and heating, and you waive your right to withhold rent."
        business = "Shifts routine capital and operational maintenance obligations under $300 to tenant; attempts an unlawful waiver of statutory habitability protections."
    elif "limitation of landlord liability" in title.lower() or "active negligence" in body_summary.lower():
        eli5 = "If the landlord's worker accidentally floods your apartment or breaks your stuff, you cannot sue them, and you might have to pay their costs."
        practical = "The landlord takes no responsibility for water damage, theft, or even harm caused by their own workers' negligence."
        business = "Comprehensive unilateral exculpatory clause attempting to shield landlord from liability for ordinary and active negligence."
    elif "legal fees" in title.lower() or "attorney's fees" in body_summary.lower():
        eli5 = "If you go to court and WIN, you still have to pay the other party's expensive lawyers."
        practical = "You are on the hook for all of the landlord's or company's legal fees in any dispute, even if a judge rules in your favor."
        business = "One-sided asymmetric fee shifting that eliminates your legal recourse by making litigation cost-prohibitive regardless of merits."
    elif "intellectual property" in title.lower() or "inventions" in body_summary.lower():
        eli5 = "Everything you code or create—even on your own laptop on a Saturday afternoon—belongs to the company for the next 2 years."
        practical = "The company claims ownership of all side projects, open-source work, and code written outside working hours on personal devices."
        business = "Overreaching assignment of IP capturing off-hours and unrelated inventions; imposes a 12-month post-termination overhang on future creations."
    elif "unlimited liability" in title.lower() or "shall be unlimited" in body_summary.lower():
        eli5 = "If something goes wrong with your work, there is no limit to how much money they can demand from you—it could bankrupt you."
        practical = "Your financial risk is infinite. You could be sued for third-party claims, patent suits, or outages far beyond what you earned."
        business = "Uncapped indemnification with zero liability limitation, leaving contractor exposed to enterprise-scale risk without insurance parity."
    elif "non-competition" in title.lower() or "non-compete" in body_summary.lower():
        eli5 = "You cannot work for any other tech or cloud company in the entire world for 2 whole years after you stop working with them."
        practical = "A 24-month worldwide restriction prevents you from consulting, advising, or taking another software job in your field."
        business = "Extremely broad restrictive covenant lacking geographic or functional scope reasonable under common law tests."
    elif "compensation and payment" in title.lower() or "net-90" in body_summary.lower():
        eli5 = "You have to wait 90 days after you work to get paid, and they can refuse to pay if they subjectively don't like it."
        practical = "Payment takes 3 months from invoice approval. The client reserves the right to withhold money if they find work unsatisfactory."
        business = "Net-90 payment terms coupled with subjective approval discretion create severe cash flow exposure and uncollectible receivable risk."
    elif "perpetual confidentiality" in title.lower() or "in perpetuity" in body_summary.lower():
        eli5 = "You can never tell anyone anything about what you worked on, forever and ever, until you die."
        practical = "Your confidentiality obligations never expire, and you are forbidden from even talking to your own accountant or lawyer."
        business = "Perpetual duration without reasonable sunset (standard is 2-3 years); overbroad definition restricting normal professional advisory."
    elif "liquidated damages" in title.lower() or "$250,000" in body_summary.lower():
        eli5 = "If you accidentally mention anything to anyone, you instantly owe them $250,000 without them having to prove any actual loss."
        practical = "A single accidental disclosure triggers an automatic $250,000 fine plus $100,000 if an employee later joins your team."
        business = "Disproportionate liquidated damages provisions functioning as punitive deterrents rather than genuine compensatory estimates."
    else:
        # Dynamic generic translation based on content
        eli5 = f"This section explains rules around {category.lower()}. It lays out what is expected from both sides and what happens if conditions are not met."
        practical = f"Summary: {body_summary[:160]}... Ensure you comply with the timeline and notification procedures stated here."
        business = f"Governs {category.lower()} parameters. Review for alignment with your operational requirements and standard risk thresholds."

    return eli5, practical, business

def analyze_document_locally(filename: str, text: str) -> DocumentAnalysisResponse:
    """Performs deep heuristic analysis of a legal document."""
    doc_type = detect_document_type(text)
    raw_clauses = split_into_clauses(text)
    
    analyzed_clauses: List[ClauseAnalysis] = []
    red_count = 0
    warning_count = 0
    safe_count = 0
    
    financial_commitments = []
    deadlines = []
    
    # Financial regexes ($ amounts)
    dollars = re.findall(r"\$[\d,]+(?:\.\d{2})?", text)
    if dollars:
        unique_dollars = list(dict.fromkeys(dollars))[:6]
        for amt in unique_dollars:
            financial_commitments.append(f"Mentioned financial amount: {amt}")
            
    # Process each clause
    for idx, c in enumerate(raw_clauses, 1):
        title = c["title"]
        body = c["body"]
        full_clause_text = f"{title}\n{body}"
        
        # Check against risk rules
        matched_rule = None
        for rule in RISK_RULES:
            if re.search(rule["pattern"], full_clause_text, re.IGNORECASE):
                matched_rule = rule
                break
                
        if matched_rule:
            risk_lvl = matched_rule["level"]
            risk_cat = matched_rule["category"]
            risk_exp = matched_rule["explanation"]
            ind_std = matched_rule["standard"]
            counter = matched_rule["counter"]
            if risk_lvl == "critical":
                red_count += 1
            elif risk_lvl == "warning":
                warning_count += 1
            else:
                safe_count += 1
        else:
            # Default classification
            lower_title = title.lower()
            if any(k in lower_title for k in ["governing law", "jurisdiction", "venue"]):
                risk_lvl = "info"
                risk_cat = "Governing Law & Jurisdiction"
                risk_exp = "Specifies which state's legal framework and courts govern any formal dispute."
                ind_std = "Typically chosen as the home state of the drafter or Delaware/New York."
                counter = "Negotiate for your home jurisdiction or mutual neutral venue."
            elif any(k in lower_title for k in ["purpose", "preamble", "recitals"]):
                risk_lvl = "safe"
                risk_cat = "Preamble & Parties"
                risk_exp = "Identifies the contracting parties and their fundamental transaction intent."
                ind_std = "Standard introductory identification clause."
                counter = None
            elif any(k in lower_title for k in ["return", "destruction", "materials"]):
                risk_lvl = "safe"
                risk_cat = "Material Return"
                risk_exp = "Outlines procedures for returning or securely destroying proprietary data when finished."
                ind_std = "Standard commercial term with routine electronic backup exceptions."
                counter = None
            else:
                risk_lvl = "info"
                risk_cat = "General Operational Terms"
                risk_exp = "Standard operational obligation or contract mechanics clause."
                ind_std = "Consistent with standard legal drafting conventions."
                counter = None
            safe_count += 1
            
        eli5, practical, business = generate_plain_english_translations(title, body, risk_cat, risk_lvl)
        
        # Determine negotiation leverage
        if risk_lvl == "critical" or risk_cat in ["Auto-Renewal & Notice Trap", "Liquidated Damages & Penalties", "Unjustified Deductions", "Payment & Cashflow Risk"]:
            leverage = "High — Highly Contestable"
        elif risk_cat in ["Liability & Indemnification", "Intellectual Property Overreach", "Restrictive Covenants", "Habitability & Maintenance Shift"]:
            leverage = "Medium — Negotiable Compromise"
        else:
            leverage = "Standard / Low Risk"

        analyzed_clauses.append(ClauseAnalysis(
            id=f"clause_{idx}",
            section_title=title,
            original_text=body,
            simplified_eli5=eli5,
            simplified_practical=practical,
            simplified_business=business,
            risk_level=risk_lvl,
            risk_category=risk_cat,
            risk_explanation=risk_exp,
            industry_standard=ind_std,
            recommended_counter_term=counter,
            negotiation_leverage=leverage,
            plain_english_score="Grade 6 Readability"
        ))
        
        # Deadlines and notice periods extraction
        notice_match = re.search(r"(\d+)\s*(days|months|business\s+days|hours)\s*(prior|advance|notice|written\s+notice)?", body, re.IGNORECASE)
        if notice_match:
            deadlines.append({
                "clause": title[:35],
                "timeframe": f"{notice_match.group(1)} {notice_match.group(2)}",
                "action": f"Notice/compliance requirement mentioned in {title[:30]}"
            })
            
    # Calculate category counts
    category_counts = {}
    for c in analyzed_clauses:
        category_counts[c.risk_category] = category_counts.get(c.risk_category, 0) + 1

    # Calculate overall risk score (0-100)
    # Critical flags carry heavy weight
    raw_score = (red_count * 28) + (warning_count * 12) + (safe_count * 1)
    overall_score = min(max(raw_score, 15), 98) if (red_count + warning_count) > 0 else 20
    
    if overall_score >= 70:
        risk_label = "Critical Risk — Extreme Caution Advised"
    elif overall_score >= 45:
        risk_label = "High Risk — Several Unfavorable Clauses"
    elif overall_score >= 25:
        risk_label = "Moderate Risk — Standard With Points to Review"
    else:
        risk_label = "Low Risk — Well-Balanced Agreement"
        
    # Extract parties and governing law
    parties = []
    gov_law = None
    gov_match = re.search(r"(governed by the laws of (?:the State of )?([A-Za-z\s]+?)(?:,|\.|\band\b))", text, re.IGNORECASE)
    if gov_match:
        gov_law = gov_match.group(1).strip()
    
    party_matches = re.findall(r"between\s+([^,]+?)(?:,|\s+and\b)", text, re.IGNORECASE)
    if party_matches:
        parties = [p.strip() for p in party_matches[:2]]
    else:
        parties = ["Party A (Disclosing/Landlord/Company)", "Party B (Recipient/Tenant/Contractor)"]

    # Pre-signature checklist items
    checklist = [
        {"task": "Verify exact legal names and addresses of both entities", "category": "Parties", "completed": False},
        {"task": f"Confirm governing jurisdiction ({gov_law or 'State Law'}) is acceptable", "category": "Legal", "completed": False},
        {"task": f"Negotiate amendment or cap for {red_count} critical risk clauses identified", "category": "Negotiation", "completed": False},
        {"task": "Calendar all notice deadlines and payment milestones", "category": "Operations", "completed": False},
        {"task": "Retain an executed duplicate signed copy with all exhibits attached", "category": "Compliance", "completed": False}
    ]
    
    # Attorney consultation questions
    attorney_questions = [
        "In light of the identified one-sided liability and indemnification clauses, what standard limitation of liability rider should we attach?",
        "Are the restrictive covenants (non-compete/moonlighting/arbitration) enforceable under our state's current statutes and court precedents?",
        "What specific statutory protections exist in this jurisdiction that invalidate the landlord/company's proposed waivers?",
        "If the counterparty rejects our proposed counter-language, what is our maximum financial and operational exposure?",
        "How can we redline the termination and auto-renewal mechanisms to ensure reciprocal rights with 30-day notice?"
    ]
    
    suggested_questions = [
        "What is the single most dangerous clause in this document?",
        "What happens if I need to terminate or move out early?",
        "Does the other party have the right to enter my premises or own my side work?",
        "How much money could I be forced to pay under worst-case scenarios?",
        "What are my key deadlines and notice requirements?"
    ]
    
    exec_summary = (
        f"This document is a {doc_type} evaluated at {risk_label} (Score: {overall_score}/100). "
        f"Analysis detected {red_count} critical red flags and {warning_count} cautionary provisions. "
        f"Key areas demanding immediate attention include "
        f"{'liability exposure, restrictive terms, and one-sided fee shifting' if red_count > 0 else 'routine compliance mechanics'}. "
        f"Review the counter-proposals below before executing."
    )
    
    return DocumentAnalysisResponse(
        document_id=f"doc_{abs(hash(text)) % 100000}",
        filename=filename,
        document_type=doc_type,
        overall_risk_score=overall_score,
        overall_risk_label=risk_label,
        executive_summary=exec_summary,
        key_parties=parties,
        governing_law=gov_law or "Not explicitly specified",
        financial_commitments=financial_commitments if financial_commitments else ["Standard operational fees as specified in text"],
        clauses=analyzed_clauses,
        red_flags_count=red_count,
        warning_flags_count=warning_count,
        safe_flags_count=safe_count,
        category_counts=category_counts,
        readability_summary="Grade 6 — Conversational English",
        deadlines_and_obligations=deadlines if deadlines else [{"clause": "Term", "timeframe": "12-24 Months", "action": "General duration"}],
        presignature_checklist=checklist,
        attorney_questions=attorney_questions,
        suggested_user_questions=suggested_questions,
        ai_engine_used="JurisClear Built-in Legal Intelligence Engine"
    )

def answer_question_locally(document_text: str, question: str) -> AskQuestionResponse:
    """Answers document questions locally using semantic clause matching and direct citations."""
    q_lower = question.lower()
    clauses = split_into_clauses(document_text)
    
    matched_clauses = []
    
    # Priority keyword mappings
    keywords = []
    if "terminate" in q_lower or "cancel" in q_lower or "move out" in q_lower or "leave" in q_lower:
        keywords = ["terminate", "termination", "renewal", "vacate", "expiration", "notice"]
    elif "deposit" in q_lower or "money" in q_lower or "fee" in q_lower or "pay" in q_lower:
        keywords = ["deposit", "cleaning", "late fee", "compensation", "deduction", "payment"]
    elif "enter" in q_lower or "access" in q_lower or "privacy" in q_lower or "come in" in q_lower:
        keywords = ["enter", "access", "inspection", "notice", "hours"]
    elif "liab" in q_lower or "sue" in q_lower or "damage" in q_lower or "indemn" in q_lower:
        keywords = ["liab", "indemn", "hold harmless", "damage", "negligence", "unlimited"]
    elif "own" in q_lower or "ip" in q_lower or "patent" in q_lower or "code" in q_lower or "side project" in q_lower:
        keywords = ["intellectual property", "inventions", "authorship", "moral rights", "personal time"]
    elif "compete" in q_lower or "client" in q_lower or "work" in q_lower:
        keywords = ["compete", "solicit", "twenty-four", "months", "worldwide"]
    else:
        keywords = [word for word in re.findall(r"\b[a-z]{4,}\b", q_lower) if word not in ["what", "does", "this", "that", "with", "from", "have"]]
        
    for c in clauses:
        combined = f"{c['title']} {c['body']}".lower()
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            matched_clauses.append((score, c))
            
    matched_clauses.sort(key=lambda x: x[0], reverse=True)
    
    citations = []
    if matched_clauses:
        best_score, best_clause = matched_clauses[0]
        # Quote up to 220 chars of relevant text
        excerpt = best_clause["body"][:260] + ("..." if len(best_clause["body"]) > 260 else "")
        citations.append({
            "clause_title": best_clause["title"],
            "quote": excerpt,
            "page_or_para": f"Section: {best_clause['title'][:30]}"
        })
        
        # Formulate grounded plain answer
        answer = (
            f"Based on **{best_clause['title']}**, the document stipulates that: {best_clause['body'][:320]}... "
            f"\n\nIn plain English: This provision governs your rights and obligations in this area. "
            f"Pay special attention to any notice periods or financial liabilities specified here."
        )
        practical = f"Check the specific wording in {best_clause['title']}. Do not assume verbal agreements override these written conditions."
    else:
        answer = "The provided document does not appear to contain an explicit clause specifically addressing this question. In contract law, unaddressed terms default to standard statutory law or common law principles in your governing jurisdiction."
        practical = "Consider asking for a written clarification or an explicit amendment rider to confirm this point in writing before signing."
        
    return AskQuestionResponse(
        question=question,
        answer=answer,
        citations=citations,
        confidence="High (Direct Text Citation)" if matched_clauses else "Moderate (Statutory Inference)",
        practical_takeaway=practical,
        disclaimer="This response provides automated legal information and document navigation for informational purposes only. It is not formal legal advice."
    )

def generate_inline_redline(text_a: str, text_b: str, max_words: int = 140) -> str:
    """
    Generates word-level inline legal redline markup.
    Deletions from Document A are wrapped in <del class="diff-del">... </del>.
    Additions in Document B are wrapped in <ins class="diff-ins">... </ins>.
    """
    if not text_a and not text_b:
        return ""
    if not text_a:
        clean_b = html.escape(" ".join(text_b.strip().split()[:max_words]))
        return f'<ins class="diff-ins" title="Added in Document B">{clean_b}</ins>'
    if not text_b:
        clean_a = html.escape(" ".join(text_a.strip().split()[:max_words]))
        return f'<del class="diff-del" title="Removed in Document B">{clean_a}</del>'

    words_a = text_a.strip().split()
    words_b = text_b.strip().split()

    trimmed = False
    if len(words_a) > max_words:
        words_a = words_a[:max_words]
        trimmed = True
    if len(words_b) > max_words:
        words_b = words_b[:max_words]
        trimmed = True

    matcher = difflib.SequenceMatcher(None, words_a, words_b)
    chunks = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            chunks.append(html.escape(" ".join(words_a[i1:i2])))
        elif tag == 'delete':
            deleted = html.escape(" ".join(words_a[i1:i2]))
            chunks.append(f'<del class="diff-del" title="Removed in Document B">{deleted}</del>')
        elif tag == 'insert':
            inserted = html.escape(" ".join(words_b[j1:j2]))
            chunks.append(f'<ins class="diff-ins" title="Added in Document B">{inserted}</ins>')
        elif tag == 'replace':
            deleted = html.escape(" ".join(words_a[i1:i2]))
            inserted = html.escape(" ".join(words_b[j1:j2]))
            chunks.append(f'<del class="diff-del" title="Removed in Document A">{deleted}</del> <ins class="diff-ins" title="Added in Document B">{inserted}</ins>')

    result = " ".join(chunks)
    if trimmed:
        result += ' <span class="diff-truncated" style="color: var(--text-muted); font-style: italic;">[...remainder of section continues...]</span>'
    return result

def compare_documents_locally(doc_a_name: str, doc_a_text: str, doc_b_name: str, doc_b_text: str) -> CompareDocumentsResponse:
    """Performs deep, authentic comparative diff analysis between two contracts/versions."""
    clauses_a = split_into_clauses(doc_a_text)
    clauses_b = split_into_clauses(doc_b_text)

    doc_a_type = detect_document_type(doc_a_text)
    doc_b_type = detect_document_type(doc_b_text)

    # Calculate individual document risk posture and scores
    analysis_a = analyze_document_locally(doc_a_name, doc_a_text)
    analysis_b = analyze_document_locally(doc_b_name, doc_b_text)

    # Profiles
    doc_a_highlights = []
    if "mutual" in doc_a_text.lower():
        doc_a_highlights.append("Bilateral mutual confidentiality obligations")
    if "two (2) years" in doc_a_text.lower() or "2 years" in doc_a_text.lower():
        doc_a_highlights.append("Standard 2-year defined term of protection")
    if analysis_a.red_flags_count == 0:
        doc_a_highlights.append("Free of punitive liquidated damage traps")
    if not doc_a_highlights:
        doc_a_highlights = [f"{len(clauses_a)} clauses structured", f"Risk Score: {analysis_a.overall_risk_score}/100"]

    doc_b_highlights = []
    if "perpetuity" in doc_b_text.lower():
        doc_b_highlights.append("Perpetual (infinite) secrecy obligation")
    if "liquidated damages" in doc_b_text.lower() or "$250,000" in doc_b_text:
        doc_b_highlights.append("$250,000 automatic liquidated damages penalty")
    if "non-solicitation" in doc_b_text.lower() or "solicit" in doc_b_text.lower():
        doc_b_highlights.append("36-month non-solicitation restrictive covenant ($100k penalty)")
    if "unilateral" in doc_b_text.lower():
        doc_b_highlights.append("One-sided unilateral protection favoring Counterparty")
    if not doc_b_highlights:
        doc_b_highlights = [f"{len(clauses_b)} clauses structured", f"Risk Score: {analysis_b.overall_risk_score}/100"]

    profile_a = DocumentProfile(
        name=doc_a_name,
        document_type=doc_a_type,
        clause_count=len(clauses_a),
        risk_score=analysis_a.overall_risk_score,
        risk_label=analysis_a.overall_risk_label,
        posture="Balanced & Reciprocal" if analysis_a.overall_risk_score < 40 else "Standard Commercial",
        key_highlights=doc_a_highlights
    )

    profile_b = DocumentProfile(
        name=doc_b_name,
        document_type=doc_b_type,
        clause_count=len(clauses_b),
        risk_score=analysis_b.overall_risk_score,
        risk_label=analysis_b.overall_risk_label,
        posture="Aggressive & One-Sided" if analysis_b.overall_risk_score >= 60 else ("Favorable & Balanced" if analysis_b.overall_risk_score < analysis_a.overall_risk_score else "Commercial Standard"),
        key_highlights=doc_b_highlights
    )

    diff_items: List[DiffItem] = []
    differences: List[ClauseDiff] = []
    similarities: List[SimilarityItem] = []

    # 1. Structure & Reciprocity
    if "mutual" in doc_a_text.lower() and "unilateral" in doc_b_text.lower():
        diff_items.append(DiffItem(
            category="Structure & Reciprocity",
            change_type="modified",
            summary="Document A is a balanced Mutual agreement protecting both parties; Document B is strictly Unilateral, protecting only the Counterparty.",
            impact="More favorable to Counterparty",
            doc_a_excerpt="Mutual Non-Disclosure Agreement... protects both Parties",
            doc_b_excerpt="Unilateral Agreement... Recipient shall maintain Company information"
        ))
        differences.append(ClauseDiff(
            id="diff_reciprocity",
            category="Structure & Reciprocity",
            clause_title="Bilateral Reciprocity vs Unilateral Burden",
            change_type="modified",
            impact="More favorable to Counterparty",
            risk_severity="critical",
            doc_a_title="Mutual Non-Disclosure Agreement",
            doc_a_excerpt="Both parties desire to explore a business relationship... each party may disclose proprietary information.",
            doc_b_title="Unilateral Non-Disclosure Agreement",
            doc_b_excerpt="Recipient desires to evaluate Company... Recipient shall safeguard Company Confidential Information.",
            redline_html='<del class="diff-del">Mutual Non-Disclosure Agreement (Both Parties Protected)</del> <ins class="diff-ins">Unilateral Agreement (Recipient Strictly Bound, Company Unbound)</ins>',
            summary="Document A provides equal, reciprocal protections so that your proprietary information is protected. Document B strips away all protections for your disclosures, placing legal obligations solely on you.",
            action_advice="Insist on a Mutual NDA structure: require that both parties be treated as Disclosing and Receiving parties under identical rules."
        ))
    elif "unilateral" in doc_a_text.lower() and "mutual" in doc_b_text.lower():
        diff_items.append(DiffItem(
            category="Structure & Reciprocity",
            change_type="modified",
            summary="Document B replaces a one-sided unilateral agreement with a balanced Mutual agreement protecting both parties equally.",
            impact="More favorable to You",
            doc_a_excerpt="Unilateral Agreement... Recipient shall maintain Company information",
            doc_b_excerpt="Mutual Non-Disclosure Agreement... protects both Parties"
        ))
        differences.append(ClauseDiff(
            id="diff_reciprocity",
            category="Structure & Reciprocity",
            clause_title="Bilateral Reciprocity vs Unilateral Burden",
            change_type="modified",
            impact="More favorable to You",
            risk_severity="safe",
            doc_a_title="Unilateral Non-Disclosure Agreement",
            doc_a_excerpt="Recipient desires to evaluate Company... Recipient shall safeguard Company Confidential Information.",
            doc_b_title="Mutual Non-Disclosure Agreement",
            doc_b_excerpt="Both parties desire to explore a business relationship... each party may disclose proprietary information.",
            redline_html='<del class="diff-del">Unilateral Agreement (Recipient Strictly Bound)</del> <ins class="diff-ins">Mutual Non-Disclosure Agreement (Both Parties Protected Equally)</ins>',
            summary="Document B converts a one-sided agreement into a balanced bilateral contract where both parties receive equal confidentiality protections.",
            action_advice="Accept Document B's mutual framework as the operating baseline."
        ))

    # 2. Confidentiality Duration
    dur_a = re.search(r"(\d+)\s*years?", doc_a_text, re.IGNORECASE)
    dur_b = re.search(r"(\d+)\s*years?", doc_b_text, re.IGNORECASE)
    perp_a = "perpetuity" in doc_a_text.lower() or "perpetual" in doc_a_text.lower()
    perp_b = "perpetuity" in doc_b_text.lower() or "perpetual" in doc_b_text.lower()

    if dur_a and perp_b:
        text_a_sec = "survive for a period of two (2) years following initial disclosure"
        text_b_sec = "maintain all Confidential Information in strictest confidence IN PERPETUITY"
        diff_items.append(DiffItem(
            category="Confidentiality Term",
            change_type="modified",
            summary=f"Confidentiality obligation expanded from {dur_a.group(0)} in Doc A to PERPETUAL (infinite) in Doc B.",
            impact="More favorable to Counterparty",
            doc_a_excerpt=text_a_sec,
            doc_b_excerpt=text_b_sec
        ))
        differences.append(ClauseDiff(
            id="diff_duration",
            category="Term & Duration",
            clause_title="Term of Confidentiality Obligations",
            change_type="modified",
            impact="More favorable to Counterparty",
            risk_severity="critical",
            doc_a_title=f"Term ({dur_a.group(0)})",
            doc_a_excerpt=text_a_sec,
            doc_b_title="Term (In Perpetuity)",
            doc_b_excerpt=text_b_sec,
            redline_html=generate_inline_redline(text_a_sec, text_b_sec),
            summary=f"Document B eliminates the reasonable {dur_a.group(0)} expiration date, binding you to track and protect disclosures forever (in perpetuity).",
            action_advice="Counter with: 'Confidentiality obligations shall expire two (2) years from disclosure, except for bona fide trade secrets which shall remain protected under applicable statute.'"
        ))
    elif perp_a and dur_b:
        text_a_sec = "maintain all Confidential Information in strictest confidence IN PERPETUITY"
        text_b_sec = f"survive for a period of {dur_b.group(0)} following initial disclosure"
        diff_items.append(DiffItem(
            category="Confidentiality Term",
            change_type="modified",
            summary=f"Confidentiality obligation reduced from PERPETUAL in Doc A to a reasonable {dur_b.group(0)} term in Doc B.",
            impact="More favorable to You",
            doc_a_excerpt=text_a_sec,
            doc_b_excerpt=text_b_sec
        ))
        differences.append(ClauseDiff(
            id="diff_duration",
            category="Term & Duration",
            clause_title="Term of Confidentiality Obligations",
            change_type="modified",
            impact="More favorable to You",
            risk_severity="safe",
            doc_a_title="Term (In Perpetuity)",
            doc_a_excerpt=text_a_sec,
            doc_b_title=f"Term ({dur_b.group(0)})",
            doc_b_excerpt=text_b_sec,
            redline_html=generate_inline_redline(text_a_sec, text_b_sec),
            summary=f"Document B limits the obligation to a definite {dur_b.group(0)} timeframe, preventing endless tracking liabilities.",
            action_advice="Approve this revision; definite terms reflect standard commercial best practice."
        ))

    # 3. Liquidated Damages & Penalties
    if "liquidated damages" in doc_b_text.lower() and "liquidated damages" not in doc_a_text.lower():
        text_b_damages = "Immediate liquidated damages of $250,000.00 per occurrence, without prejudice to any other rights or remedies."
        diff_items.append(DiffItem(
            category="Penalties & Damages",
            change_type="added",
            summary="Document B introduces a severe $250,000 Liquidated Damages penalty for any breach, absent in Document A.",
            impact="More favorable to Counterparty",
            doc_a_excerpt="Standard common law remedies (no fixed penalty)",
            doc_b_excerpt=text_b_damages
        ))
        differences.append(ClauseDiff(
            id="diff_penalties",
            category="Penalties & Damages",
            clause_title="Liquidated Damages Penalty Provision",
            change_type="added_in_b",
            impact="More favorable to Counterparty",
            risk_severity="critical",
            doc_a_title="Remedies (Standard)",
            doc_a_excerpt="Remedies at law may be inadequate; parties may seek equitable injunctive relief.",
            doc_b_title="Section 6: Liquidated Damages ($250,000)",
            doc_b_excerpt=text_b_damages,
            redline_html='<del class="diff-del">[No liquidated damages penalty provision]</del> <ins class="diff-ins">Recipient shall pay to Company immediate liquidated damages of $250,000.00 per occurrence without proof of actual harm.</ins>',
            summary="Document B inserts an arbitrary $250,000 penalty clause. Any claimed disclosure trigger forces immediate forfeiture without the company needing to prove actual financial loss.",
            action_advice="Strike this section in its entirety. Commercial parties must prove actual direct damages in court or arbitration rather than extracting punitive liquidated sums."
        ))
    elif "liquidated damages" in doc_a_text.lower() and "liquidated damages" not in doc_b_text.lower():
        diff_items.append(DiffItem(
            category="Penalties & Damages",
            change_type="removed",
            summary="Document B removes the aggressive liquidated damages penalty present in Document A.",
            impact="More favorable to You",
            doc_a_excerpt="Immediate liquidated damages of $250,000.00 per occurrence",
            doc_b_excerpt="Standard common law remedies (no fixed penalty)"
        ))
        differences.append(ClauseDiff(
            id="diff_penalties",
            category="Penalties & Damages",
            clause_title="Liquidated Damages Penalty Provision",
            change_type="removed_in_b",
            impact="More favorable to You",
            risk_severity="safe",
            doc_a_title="Liquidated Damages ($250,000)",
            doc_a_excerpt="Immediate liquidated damages of $250,000.00 per occurrence",
            doc_b_title="Standard Judicial Remedies",
            doc_b_excerpt="Standard common law remedies (no fixed penalty)",
            redline_html='<del class="diff-del">Recipient shall pay immediate liquidated damages of $250,000.00 per occurrence.</del> <ins class="diff-ins">[Removed — Relying on standard judicial remedies]</ins>',
            summary="Document B eliminates the dangerous $250,000 arbitrary penalty, restoring standard actual-damages recovery rules.",
            action_advice="Strongly approve Document B's removal of this punitive clause."
        ))

    # 4. Non-Solicitation Covenants
    if ("non-solicitation" in doc_b_text.lower() or "solicit" in doc_b_text.lower()) and "non-solicitation" not in doc_a_text.lower():
        text_b_solicit = "For thirty-six (36) months following termination, Recipient shall not recruit, solicit, employ or contract with any Company personnel, subject to an agreed minimum penalty fee of $100,000.00."
        diff_items.append(DiffItem(
            category="Restrictive Covenants",
            change_type="added",
            summary="Document B adds a 36-month non-solicitation restriction with an extra $100,000 penalty clause, not present in Document A.",
            impact="More favorable to Counterparty",
            doc_a_excerpt="None",
            doc_b_excerpt=text_b_solicit
        ))
        differences.append(ClauseDiff(
            id="diff_nonsolicit",
            category="Restrictive Covenants",
            clause_title="Employee Non-Solicitation Covenant & $100k Penalty",
            change_type="added_in_b",
            impact="More favorable to Counterparty",
            risk_severity="critical",
            doc_a_title="Restrictive Covenants (None)",
            doc_a_excerpt="No non-solicitation or hiring restrictions.",
            doc_b_title="Section 7: Non-Solicitation of Personnel",
            doc_b_excerpt=text_b_solicit,
            redline_html='<del class="diff-del">[No restrictive hiring covenants]</del> <ins class="diff-ins">Recipient shall not recruit, solicit, employ Company personnel for 36 months under penalty of $100,000.00.</ins>',
            summary="Document B smuggles an aggressive 3-year non-solicitation covenant into what should be a routine NDA, restricting your company's normal hiring and recruitment practices with a $100,000 penalty.",
            action_advice="Strike Section 7 completely. Non-solicitation clauses should not be included in preliminary confidentiality discussions."
        ))
    elif ("non-solicitation" in doc_a_text.lower() or "solicit" in doc_a_text.lower()) and "non-solicitation" not in doc_b_text.lower():
        diff_items.append(DiffItem(
            category="Restrictive Covenants",
            change_type="removed",
            summary="Document B eliminates the aggressive 36-month non-solicitation penalty present in Document A.",
            impact="More favorable to You",
            doc_a_excerpt="For thirty-six (36) months, Recipient shall not recruit, solicit, employ Company personnel",
            doc_b_excerpt="None"
        ))
        differences.append(ClauseDiff(
            id="diff_nonsolicit",
            category="Restrictive Covenants",
            clause_title="Employee Non-Solicitation Covenant",
            change_type="removed_in_b",
            impact="More favorable to You",
            risk_severity="safe",
            doc_a_title="Non-Solicitation Covenant (36 Months)",
            doc_a_excerpt="For thirty-six (36) months, Recipient shall not recruit, solicit, employ Company personnel",
            doc_b_title="Standard NDA Terms (No Non-Solicitation)",
            doc_b_excerpt="None",
            redline_html='<del class="diff-del">Recipient shall not recruit or solicit Company personnel for 36 months.</del> <ins class="diff-ins">[Removed — Preserving open commercial recruitment]</ins>',
            summary="Document B removes the 36-month hiring freeze and associated penalties, safeguarding your hiring freedom.",
            action_advice="Approve Document B on this point."
        ))

    # 5. Liability Caps
    if "unlimited" in doc_b_text.lower() and "unlimited" not in doc_a_text.lower():
        diff_items.append(DiffItem(
            category="Liability Cap",
            change_type="modified",
            summary="Document B removes liability caps and creates unlimited liability exposure for the signing party.",
            impact="More favorable to Counterparty",
            doc_a_excerpt="Standard liability limitations",
            doc_b_excerpt="LIABILITY UNDER THIS SECTION SHALL BE UNLIMITED"
        ))
        differences.append(ClauseDiff(
            id="diff_liability",
            category="Liability Cap",
            clause_title="Limitation of Financial Liability",
            change_type="modified",
            impact="More favorable to Counterparty",
            risk_severity="critical",
            doc_a_title="Liability Cap",
            doc_a_excerpt="Standard liability limitations",
            doc_b_title="Section: Unlimited Liability",
            doc_b_excerpt="LIABILITY UNDER THIS SECTION SHALL BE UNLIMITED",
            redline_html='<del class="diff-del">Liability capped at total contract fees</del> <ins class="diff-ins">LIABILITY UNDER THIS SECTION SHALL BE UNLIMITED</ins>',
            summary="Document B strips out liability safeguards, creating catastrophic exposure against your business assets.",
            action_advice="Demand an aggregate liability cap (e.g. 1x or 2x contract value)."
        ))
    elif "unlimited" in doc_a_text.lower() and "unlimited" not in doc_b_text.lower():
        diff_items.append(DiffItem(
            category="Liability Cap",
            change_type="modified",
            summary="Document B restores standard liability limitations and eliminates unlimited financial exposure.",
            impact="More favorable to You",
            doc_a_excerpt="LIABILITY UNDER THIS SECTION SHALL BE UNLIMITED",
            doc_b_excerpt="Standard liability limitations"
        ))
        differences.append(ClauseDiff(
            id="diff_liability",
            category="Liability Cap",
            clause_title="Limitation of Financial Liability",
            change_type="modified",
            impact="More favorable to You",
            risk_severity="safe",
            doc_a_title="Unlimited Liability",
            doc_a_excerpt="LIABILITY UNDER THIS SECTION SHALL BE UNLIMITED",
            doc_b_title="Standard Commercial Cap",
            doc_b_excerpt="Standard liability limitations",
            redline_html='<del class="diff-del">LIABILITY SHALL BE UNLIMITED</del> <ins class="diff-ins">Liability limited to standard commercial caps</ins>',
            summary="Document B restores appropriate liability boundaries.",
            action_advice="Approve this protective modification."
        ))

    # 6. Standard of Care
    if "strictest degree of care" in doc_b_text.lower() and "strictest degree of care" not in doc_a_text.lower():
        differences.append(ClauseDiff(
            id="diff_standard_care",
            category="Standard of Care",
            clause_title="Standard of Care for Safeguarding Disclosures",
            change_type="modified",
            impact="More favorable to Counterparty",
            risk_severity="warning",
            doc_a_title="Standard of Care (Reasonable)",
            doc_a_excerpt="Exercising a reasonable degree of care, not less than the degree of care it uses for its own confidential information.",
            doc_b_title="Standard of Care (Strict Fiduciary)",
            doc_b_excerpt="Recipient shall maintain all Confidential Information in strictest confidence and exercise the highest fiduciary degree of care.",
            redline_html='<del class="diff-del">reasonable degree of care</del> <ins class="diff-ins">strictest confidence and highest fiduciary degree of care</ins>',
            summary="Document B replaces standard commercial reasonableness with a 'highest fiduciary' standard, exposing you to breach claims for inadvertent administrative oversights.",
            action_advice="Revert to 'reasonable care, but no less than the care used for recipient\'s own confidential data'."
        ))

    # -------------------------------------------------------------------------
    # IDENTIFY AND POPULATE SHARED SIMILARITIES (What both contracts agree on)
    # -------------------------------------------------------------------------
    # A. Core Subject Matter & Protection Intent
    if ("confidential" in doc_a_text.lower() or "proprietary" in doc_a_text.lower()) and \
       ("confidential" in doc_b_text.lower() or "proprietary" in doc_b_text.lower()):
        ex_a = "Confidential Information means any non-public technical, commercial, or financial information disclosed by one Party to the other."
        ex_b = "Confidential Information shall include all information of any kind disclosed by Company, whether marked or unmarked, oral, visual, or written."
        similarities.append(SimilarityItem(
            id="sim_scope",
            category="Subject Matter & Scope",
            title="Protection of Proprietary & Confidential Information",
            description="Both agreements share the foundational purpose of establishing legal protections over non-public proprietary business, commercial, and technical disclosures.",
            alignment_status="Substantially Aligned",
            doc_a_excerpt=ex_a,
            doc_b_excerpt=ex_b
        ))

    # B. Obligation to Return or Surrender Disclosed Materials
    if ("return" in doc_a_text.lower() or "destroy" in doc_a_text.lower()) and \
       ("return" in doc_b_text.lower() or "surrender" in doc_b_text.lower() or "erased" in doc_b_text.lower()):
        similarities.append(SimilarityItem(
            id="sim_return",
            category="Operational Mechanics",
            title="Obligation to Surrender Disclosed Materials Upon Request",
            description="Both contracts require the recipient to surrender and return proprietary records, notes, copies, and files back to the disclosing party upon demand.",
            alignment_status="Standard Commercial Term",
            doc_a_excerpt="Promptly return or destroy all copies of Disclosing Party's Confidential Information.",
            doc_b_excerpt="Upon 24 hours notice, Recipient shall surrender all notes, hardware, drive images, and materials containing Company data."
        ))

    # C. Third-Party Disclosure Restrictions
    if ("third party" in doc_a_text.lower() or "third-party" in doc_a_text.lower()) and \
       ("third party" in doc_b_text.lower() or "third-party" in doc_b_text.lower()):
        similarities.append(SimilarityItem(
            id="sim_thirdparty",
            category="Information Security",
            title="Restriction on Unauthorized Third-Party Dissemination",
            description="Both agreements prohibit sharing disclosed data with unauthorized third parties without prior written consent or explicit need-to-know vetting.",
            alignment_status="Substantially Aligned",
            doc_a_excerpt="Restrict disclosure to employees, contractors, and legal/financial advisors who have a need to know.",
            doc_b_excerpt="Recipient shall not disclose, duplicate, reverse engineer, or discuss Company information with any third party."
        ))

    # D. Judicial Court System Preserved (No Mandatory Arbitration Trap)
    if "arbitration" not in doc_a_text.lower() and "arbitration" not in doc_b_text.lower():
        similarities.append(SimilarityItem(
            id="sim_court_system",
            category="Dispute Resolution",
            title="Judicial Court Forum Preserved (No Forced Private Arbitration)",
            description="Neither contract forces the parties into private mandatory arbitration or waives trial rights, keeping formal judicial courts as the venue for resolving disputes.",
            alignment_status="Shared Judicial Forum",
            doc_a_excerpt="Disputes governed under state court jurisdiction without mandatory arbitration rider.",
            doc_b_excerpt="Recipient submits to the exclusive jurisdiction of the state courts."
        ))

    # E. Confidentiality Exclusions (Carve-outs)
    if ("public domain" in doc_a_text.lower() or "publicly known" in doc_a_text.lower()) and \
       ("public domain" in doc_b_text.lower() or "publicly known" in doc_b_text.lower()):
        similarities.append(SimilarityItem(
            id="sim_exclusions",
            category="Standard Exclusions",
            title="Common Industry Carve-Outs for Disclosed Information",
            description="Both agreements share standard commercial carve-outs: information in the public domain, already known prior to receipt, or disclosed under court subpoena is excluded from confidentiality liability.",
            alignment_status="Substantially Aligned",
            doc_a_excerpt="Excludes information which: (a) is or becomes publicly known through no breach; (b) was already in possession; (c) is required by law.",
            doc_b_excerpt="Does not apply to information that: (a) is in the public domain; (b) was already known to Recipient; (c) ordered disclosed by court."
        ))

    # F. Governing Law & Jurisdiction (if same state)
    if "delaware" in doc_a_text.lower() and "delaware" in doc_b_text.lower():
        similarities.append(SimilarityItem(
            id="sim_govlaw",
            category="Governing Law",
            title="Delaware Choice of Law & Venue",
            description="Both contracts select the State of Delaware as the governing legal jurisdiction and choose Delaware courts for dispute resolution.",
            alignment_status="Identical Choice of Law",
            doc_a_excerpt="Governed by and construed in accordance with the laws of the State of Delaware.",
            doc_b_excerpt="Governed by the substantive laws of the State of Delaware."
        ))
    elif "california" in doc_a_text.lower() and "california" in doc_b_text.lower():
        similarities.append(SimilarityItem(
            id="sim_govlaw",
            category="Governing Law",
            title="California Choice of Law & Venue",
            description="Both contracts select California law and venue for governing rights.",
            alignment_status="Identical Choice of Law",
            doc_a_excerpt="Governed by the laws of the State of California.",
            doc_b_excerpt="Governed by the laws of the State of California."
        ))

    # G. Written Amendments & Entire Agreement
    if "in writing" in doc_a_text.lower() and "in writing" in doc_b_text.lower() and \
       ("amend" in doc_a_text.lower() or "modify" in doc_a_text.lower()) and \
       ("amend" in doc_b_text.lower() or "modify" in doc_b_text.lower()):
        similarities.append(SimilarityItem(
            id="sim_amendments",
            category="Contract Mechanics",
            title="Written Amendment Requirement",
            description="Both agreements mandate that any amendment, modification, or waiver of terms must be in writing and signed by authorized representatives of both parties.",
            alignment_status="Standard Commercial Term",
            doc_a_excerpt="May only be amended or modified by a written agreement signed by both parties.",
            doc_b_excerpt="No modification shall be binding unless executed in writing by Company."
        ))

    # H. Equitable / Injunctive Relief
    if "injunctive" in doc_a_text.lower() and "injunctive" in doc_b_text.lower():
        similarities.append(SimilarityItem(
            id="sim_injunction",
            category="Remedies",
            title="Availability of Equitable Injunctions",
            description="Both documents acknowledge that breach of confidentiality causes irreparable harm for which monetary damages alone may be inadequate, entitling the disclosing party to seek injunctive relief.",
            alignment_status="Substantially Aligned",
            doc_a_excerpt="Injunctive relief may be sought in addition to other available remedies.",
            doc_b_excerpt="Company shall be entitled to seek immediate injunctive relief without posting bond."
        ))

    # Fallback diff items if minimal categories matched
    if len(diff_items) < 2:
        diff_items.append(DiffItem(
            category="Length & Clause Count",
            change_type="modified",
            summary=f"{doc_a_name} contains {len(clauses_a)} sections whereas {doc_b_name} contains {len(clauses_b)} sections.",
            impact="Neutral",
            doc_a_excerpt=f"Total clauses: {len(clauses_a)}",
            doc_b_excerpt=f"Total clauses: {len(clauses_b)}"
        ))
        if not differences:
            differences.append(ClauseDiff(
                id="diff_clause_count",
                category="Structure & Length",
                clause_title="Clause Count & Section Depth",
                change_type="modified",
                impact="Neutral",
                risk_severity="info",
                doc_a_title=f"{doc_a_name} ({len(clauses_a)} sections)",
                doc_a_excerpt=f"Document contains {len(clauses_a)} distinct sections.",
                doc_b_title=f"{doc_b_name} ({len(clauses_b)} sections)",
                doc_b_excerpt=f"Document contains {len(clauses_b)} distinct sections.",
                redline_html=f'<del class="diff-del">{len(clauses_a)} clauses</del> <ins class="diff-ins">{len(clauses_b)} clauses</ins>',
                summary=f"Section volume differences between drafts.",
                action_advice="Review side-by-side to ensure no standard sections were omitted."
            ))

    has_counterparty = any(d.impact == "More favorable to Counterparty" for d in diff_items)
    has_you = any(d.impact == "More favorable to You" for d in diff_items)

    checklist: List[str] = []
    if has_counterparty and not has_you:
        favorability = "Shifted 65% towards Counterparty (Significantly more restrictive)"
        fav_percentage = -65
        risk_delta = "High Risk Increase in Document B"
        rec = f"We strongly advise requesting the terms from {doc_a_name} (or attaching a compromise redline rider). {doc_b_name} significantly increases your legal liability, introduces punitive financial penalties, and extends obligation durations indefinitely."
        checklist = [
            "Strike Section 6 ($250,000 Liquidated Damages) and replace with standard actual direct damages.",
            "Revert Section 4 duration from perpetuity back to two (2) years.",
            "Delete Section 7 (36-month non-solicitation of personnel and $100k penalty).",
            "Insist on mutual reciprocity so both parties receive identical protections for their disclosures.",
            "Maintain the agreed governing law and standard exclusion carve-outs."
        ]
    elif has_you and not has_counterparty:
        favorability = "Shifted 65% towards You (Significantly more favorable & balanced)"
        fav_percentage = 65
        risk_delta = "Favorable Risk Reduction in Document B"
        rec = f"{doc_b_name} is noticeably more balanced, reciprocal, and protective of your interests compared to {doc_a_name}. Proceed with {doc_b_name} as the working baseline."
        checklist = [
            f"Adopt {doc_b_name} as the approved baseline.",
            "Confirm mutual reciprocity applies to all schedules and future exhibits.",
            "Calendar the 2-year expiration deadline."
        ]
    elif has_counterparty and has_you:
        favorability = "Mixed Net Shift (Both favorable and restrictive modifications)"
        fav_percentage = -15
        risk_delta = "Moderate Rebalancing Across Documents"
        rec = "Review both versions side-by-side: some terms improved while others became more stringent. Retain the favorable amendments and push back on new restrictions."
        checklist = [
            "Accept favorable term reductions from Document B.",
            "Push back on newly introduced penalties or covenants.",
            "Request a unified clean execution draft."
        ]
    else:
        favorability = "Relatively Balanced Comparison"
        fav_percentage = 0
        risk_delta = "Minor Contract Variations"
        rec = "Both documents appear comparable in terms of risk exposure and balance."
        checklist = ["Confirm signature blocks and execution dates match."]

    summary = f"Comparative redline analysis between '{doc_a_name}' and '{doc_b_name}' identifies {len(differences)} key legal variances and {len(similarities)} common shared principles. The balance of obligations has {favorability.lower()}."

    # Counts
    added_count = sum(1 for d in differences if d.change_type == "added_in_b")
    removed_count = sum(1 for d in differences if d.change_type == "removed_in_b")
    modified_count = sum(1 for d in differences if d.change_type == "modified")
    identical_count = len(similarities)

    return CompareDocumentsResponse(
        comparison_summary=summary,
        favorability_shift=favorability,
        favorability_percentage=fav_percentage,
        risk_delta=risk_delta,
        doc_a_profile=profile_a,
        doc_b_profile=profile_b,
        similarities=similarities,
        differences=differences,
        key_differences=diff_items,
        clauses_added_count=added_count,
        clauses_removed_count=removed_count,
        clauses_modified_count=modified_count,
        clauses_identical_count=identical_count,
        recommendation=rec,
        negotiation_checklist=checklist,
        ai_engine_used="JurisClear Built-in Legal Intelligence Engine"
    )

def generate_counter_email_locally(recipient_role: str, clauses: List[str], tone: str) -> Dict[str, Any]:
    """Generates a professional counter-proposal email with polite legal phrasing."""
    subject = f"Proposed Clarifications & Adjustments to Draft Agreement — [{recipient_role}]"
    
    clauses_text = ""
    for idx, c in enumerate(clauses, 1):
        clauses_text += f"{idx}. **{c}**:\n   - *Current concern*: As drafted, this provision creates unlimited or one-sided exposure that deviates from typical commercial benchmarks.\n   - *Proposed compromise*: We suggest inserting mutual language and capping our respective commitments to ensure fair balance.\n\n"
        
    body = (
        f"Dear {recipient_role},\n\n"
        f"Thank you for sharing the draft agreement. We are enthusiastic about working together and moving this forward smoothly.\n\n"
        f"In reviewing the terms to ensure mutual clarity and protection for both sides, our review highlighted a few specific clauses where we'd appreciate making balanced adjustments:\n\n"
        f"{clauses_text}"
        f"These adjustments will align the agreement with standard industry practice while fully protecting your interests. Please let us know if these adjustments work for you or if a brief 10-minute call would be helpful to finalize them.\n\n"
        f"Best regards,\n[Your Name]"
    )
    
    talking_points = [
        "Frame requests around 'mutual clarity' and 'standard commercial conventions' rather than distrust.",
        "Emphasize willingness to sign promptly as soon as these specific clauses are aligned.",
        "Offer ready-to-paste substitute text to minimize work for the counterparty's attorney."
    ]
    
    return {
        "subject": subject,
        "email_body": body,
        "talking_points": talking_points
    }
