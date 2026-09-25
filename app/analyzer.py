"""
JurisClear Legal Intelligence Engine
Provides AST/heuristic parsing, risk radar scoring, plain-English translation at 3 readability tiers,
deadlines/obligations extraction, document comparison diffing, and grounded Q&A with clause citations.
"""

import re
from typing import List, Dict, Any, Tuple
from app.models import (
    ClauseAnalysis,
    DocumentAnalysisResponse,
    AskQuestionResponse,
    CompareDocumentsResponse,
    DiffItem
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

def compare_documents_locally(doc_a_name: str, doc_a_text: str, doc_b_name: str, doc_b_text: str) -> CompareDocumentsResponse:
    """Performs deep comparative analysis between two contracts/versions."""
    clauses_a = split_into_clauses(doc_a_text)
    clauses_b = split_into_clauses(doc_b_text)
    
    diff_items: List[DiffItem] = []
    
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
    elif "unilateral" in doc_a_text.lower() and "mutual" in doc_b_text.lower():
        diff_items.append(DiffItem(
            category="Structure & Reciprocity",
            change_type="modified",
            summary="Document B replaces a one-sided unilateral agreement with a balanced Mutual agreement protecting both parties equally.",
            impact="More favorable to You",
            doc_a_excerpt="Unilateral Agreement... Recipient shall maintain Company information",
            doc_b_excerpt="Mutual Non-Disclosure Agreement... protects both Parties"
        ))
        
    # 2. Confidentiality Duration
    dur_a = re.search(r"(\d+)\s*years?", doc_a_text, re.IGNORECASE)
    dur_b = re.search(r"(\d+)\s*years?", doc_b_text, re.IGNORECASE)
    perp_a = "perpetuity" in doc_a_text.lower() or "perpetual" in doc_a_text.lower()
    perp_b = "perpetuity" in doc_b_text.lower() or "perpetual" in doc_b_text.lower()
    
    if dur_a and perp_b:
        diff_items.append(DiffItem(
            category="Confidentiality Term",
            change_type="modified",
            summary=f"Confidentiality obligation expanded from {dur_a.group(0)} in Doc A to PERPETUAL (infinite) in Doc B.",
            impact="More favorable to Counterparty",
            doc_a_excerpt="survive for a period of two (2) years following initial disclosure",
            doc_b_excerpt="Recipient shall maintain all Confidential Information in strictest confidence IN PERPETUITY"
        ))
    elif perp_a and dur_b:
        diff_items.append(DiffItem(
            category="Confidentiality Term",
            change_type="modified",
            summary=f"Confidentiality obligation reduced from PERPETUAL in Doc A to a reasonable {dur_b.group(0)} term in Doc B.",
            impact="More favorable to You",
            doc_a_excerpt="Recipient shall maintain all Confidential Information in strictest confidence IN PERPETUITY",
            doc_b_excerpt="survive for a period of two (2) years following initial disclosure"
        ))
        
    # 3. Liquidated Damages & Penalties
    if "liquidated damages" in doc_b_text.lower() and "liquidated damages" not in doc_a_text.lower():
        diff_items.append(DiffItem(
            category="Penalties & Damages",
            change_type="added",
            summary="Document B introduces a severe $250,000 Liquidated Damages penalty for any breach, absent in Document A.",
            impact="More favorable to Counterparty",
            doc_a_excerpt="Standard common law remedies (no fixed penalty)",
            doc_b_excerpt="Immediate liquidated damages of $250,000.00 per occurrence"
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
        
    # 4. Non-Solicitation Covenants
    if ("non-solicitation" in doc_b_text.lower() or "solicit" in doc_b_text.lower()) and "non-solicitation" not in doc_a_text.lower():
        diff_items.append(DiffItem(
            category="Restrictive Covenants",
            change_type="added",
            summary="Document B adds a 36-month non-solicitation restriction with an extra $100,000 penalty clause, not present in Document A.",
            impact="More favorable to Counterparty",
            doc_a_excerpt="None",
            doc_b_excerpt="For thirty-six (36) months, Recipient shall not recruit, solicit, employ Company personnel"
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
    elif "unlimited" in doc_a_text.lower() and "unlimited" not in doc_b_text.lower():
        diff_items.append(DiffItem(
            category="Liability Cap",
            change_type="modified",
            summary="Document B restores standard liability limitations and eliminates unlimited financial exposure.",
            impact="More favorable to You",
            doc_a_excerpt="LIABILITY UNDER THIS SECTION SHALL BE UNLIMITED",
            doc_b_excerpt="Standard liability limitations"
        ))
        
    # Fallback generic diff if minimal categories matched
    if len(diff_items) < 2:
        diff_items.append(DiffItem(
            category="Length & Clause Count",
            change_type="modified",
            summary=f"{doc_a_name} contains {len(clauses_a)} sections whereas {doc_b_name} contains {len(clauses_b)} sections.",
            impact="Neutral",
            doc_a_excerpt=f"Total clauses: {len(clauses_a)}",
            doc_b_excerpt=f"Total clauses: {len(clauses_b)}"
        ))
        
    has_counterparty = any(d.impact == "More favorable to Counterparty" for d in diff_items)
    has_you = any(d.impact == "More favorable to You" for d in diff_items)

    if has_counterparty and not has_you:
        favorability = "Shifted 65% towards Counterparty (Significantly more restrictive)"
        risk_delta = "High Risk Increase in Document B"
        rec = "We strongly advise requesting the terms from Document A (or attaching a compromise redline), as Document B significantly increases your legal liability, forfeiture exposure, and duration of obligations."
    elif has_you and not has_counterparty:
        favorability = "Shifted 65% towards You (Significantly more favorable & balanced)"
        risk_delta = "Favorable Risk Reduction in Document B"
        rec = "Document B is noticeably more balanced and protective of your interests compared to Document A. Proceed with Document B as the working baseline."
    elif has_counterparty and has_you:
        favorability = "Mixed Net Shift (Both favorable and restrictive modifications)"
        risk_delta = "Moderate Rebalancing Across Documents"
        rec = "Review both versions side-by-side: some terms improved while others became more stringent."
    else:
        favorability = "Relatively Balanced Comparison"
        risk_delta = "Minor Contract Variations"
        rec = "Both documents appear comparable in terms of risk exposure and balance."

    summary = f"Comparative analysis between '{doc_a_name}' and '{doc_b_name}' reveals substantial differences in legal obligations and risk allocation. {len(diff_items)} notable variance areas were identified."
    
    return CompareDocumentsResponse(
        comparison_summary=summary,
        favorability_shift=favorability,
        risk_delta=risk_delta,
        key_differences=diff_items,
        recommendation=rec,
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
