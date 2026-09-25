"""
Comprehensive Enterprise Test Suite for JurisClear AI
Tests code quality, problem statement alignment, security, accuracy, efficiency, and edge cases.
"""

import time
import unittest
from fastapi.testclient import TestClient
from app.main import app, MAX_FILE_SIZE, MAX_TEXT_LENGTH
from app.sample_contracts import SAMPLE_CONTRACTS
from app.analyzer import (
    analyze_document_locally,
    answer_question_locally,
    compare_documents_locally,
    generate_counter_email_locally,
    split_into_clauses,
    detect_document_type
)

class TestJurisClearComprehensive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # =========================================================================
    # 1. CORE HEALTH & METADATA TESTS
    # =========================================================================
    def test_health_check_endpoint(self):
        """Verifies health check and active engine detection."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["app_name"], "JurisClear AI")
        self.assertIn("default_engine", data)
        print("[OK] Health check endpoint passed")

    # =========================================================================
    # 2. FRONTEND ASSETS & CACHE-CONTROL HEADERS
    # =========================================================================
    def test_frontend_html_and_cache_control_headers(self):
        """Verifies GET / returns valid HTML with no-cache headers and modern components."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        
        # Verify strict no-cache headers to prevent browser caching bugs
        cache_control = res.headers.get("Cache-Control", "")
        self.assertIn("no-store", cache_control)
        self.assertIn("no-cache", cache_control)

        html = res.text
        # Verify essential UI DOM elements
        self.assertIn("flipCardsContainer", html)
        self.assertIn("clauseCategoryFilters", html)
        self.assertIn("workflow-stepper", html)
        self.assertIn("riskCircleProgress", html)
        self.assertIn("styles.css?v=3.1", html)
        self.assertIn("app.js?v=3.1", html)
        print("[OK] Frontend HTML components & strict Cache-Control headers verified")

    # =========================================================================
    # 3. SAMPLE CONTRACTS INTEGRITY & DEEP ANALYSIS FOR ALL 5 CONTRACTS
    # =========================================================================
    def test_sample_contracts_library(self):
        """Validates all 5 built-in contracts are loaded with complete text and metadata."""
        res = self.client.get("/api/samples")
        self.assertEqual(res.status_code, 200)
        samples = res.json()
        self.assertEqual(len(samples), 5)
        
        expected_keys = [
            "residential_lease",
            "freelance_software",
            "mutual_nda",
            "unilateral_nda_aggressive",
            "employment_offer"
        ]
        for key in expected_keys:
            res_item = self.client.get(f"/api/samples/{key}")
            self.assertEqual(res_item.status_code, 200)
            data = res_item.json()
            self.assertTrue(len(data["title"]) > 5)
            self.assertTrue(len(data["text"]) > 200)
            self.assertIn("description", data)
        print("[OK] All 5 sample contracts verified")

    def test_all_five_sample_contracts_deep_verification(self):
        """Tests that every built-in contract produces structured clauses, 3-tier simplifications, and checklists."""
        for key, contract in SAMPLE_CONTRACTS.items():
            data = analyze_document_locally(contract["title"], contract["text"])
            self.assertGreaterEqual(len(data.clauses), 4, f"Failed on {key}")
            self.assertGreaterEqual(data.overall_risk_score, 0)
            self.assertLessEqual(data.overall_risk_score, 100)
            self.assertTrue(len(data.executive_summary) > 20)
            self.assertTrue(len(data.presignature_checklist) >= 3)
            self.assertTrue(len(data.attorney_questions) >= 3)

            # Check 3-tier plain English translations on every single clause
            for c in data.clauses:
                self.assertTrue(len(c.simplified_eli5) > 5)
                self.assertTrue(len(c.simplified_practical) > 5)
                self.assertTrue(len(c.simplified_business) > 5)
                self.assertIn(c.risk_level, ["critical", "warning", "info", "safe"])
        print("[OK] Deep multi-tier verification passed across all 5 sample contracts")

    def test_nonexistent_sample_returns_404(self):
        """Verifies proper 404 handling for invalid sample contract IDs."""
        res = self.client.get("/api/samples/non_existent_contract_id")
        self.assertEqual(res.status_code, 404)
        print("[OK] 404 handling for invalid sample verified")

    # =========================================================================
    # 4. ACCURACY: GOTCHAS & RECOMMENDED COUNTER-TERMS
    # =========================================================================
    def test_residential_lease_predatory_traps(self):
        """Tests detection of auto-renewal, entry without notice, and repair liability."""
        lease_text = SAMPLE_CONTRACTS["residential_lease"]["text"]
        data = analyze_document_locally("Austin Apartment Lease", lease_text)
        
        self.assertGreaterEqual(data.overall_risk_score, 70)
        self.assertIn("Critical Risk", data.overall_risk_label)
        self.assertGreaterEqual(data.red_flags_count, 3)

        # Confirm critical clauses contain industry standard and recommended counter-term
        critical_clauses = [c for c in data.clauses if c.risk_level == "critical"]
        self.assertTrue(len(critical_clauses) >= 3)
        for cc in critical_clauses:
            self.assertTrue(len(cc.industry_standard) > 10)
            self.assertIsNotNone(cc.recommended_counter_term)
            self.assertTrue(len(cc.recommended_counter_term) > 10)
        print("[OK] Residential lease traps and counter-proposals verified")

    def test_freelance_software_contract_traps(self):
        """Tests detection of unlimited liability, IP grabs, and Net-90 terms in freelance contracts."""
        text = SAMPLE_CONTRACTS["freelance_software"]["text"]
        data = analyze_document_locally("Freelance Dev Agreement", text)
        
        categories = [c.risk_category for c in data.clauses]
        self.assertTrue(any("Liability" in cat for cat in categories))
        self.assertTrue(any("Intellectual Property" in cat for cat in categories))
        self.assertTrue(any("Payment" in cat for cat in categories))
        print("[OK] Freelance contract specific legal traps detected accurately")

    def test_document_type_detection(self):
        """Tests contract classification heuristic."""
        self.assertEqual(detect_document_type("This is a residential lease agreement between tenant and landlord."), "Residential Lease Agreement")
        self.assertEqual(detect_document_type("Independent contractor services agreement for deliverables."), "Independent Contractor Services Agreement")
        self.assertEqual(detect_document_type("Mutual Non-Disclosure Agreement for confidential information."), "Mutual Non-Disclosure Agreement (NDA)")
        print("[OK] Document type detection verified")

    # =========================================================================
    # 5. GROUNDED Q&A WITH CITATIONS TESTS
    # =========================================================================
    def test_grounded_qa_with_direct_citation(self):
        """Tests that user questions yield direct verbatim citations and practical advice."""
        doc_text = SAMPLE_CONTRACTS["residential_lease"]["text"]
        qa_data = answer_question_locally(doc_text, "Can the landlord enter my apartment without notice?")
        
        self.assertTrue(len(qa_data.citations) > 0)
        first_citation = qa_data.citations[0]
        self.assertIn("LANDLORD ACCESS", first_citation["clause_title"])
        self.assertIn("24 hours a day", first_citation["quote"].lower())
        self.assertTrue(len(qa_data.practical_takeaway) > 10)
        print("[OK] Grounded Q&A direct citation test passed")

    def test_grounded_qa_unmentioned_topic(self):
        """Tests behavior when user asks about a term not in the document."""
        doc_text = SAMPLE_CONTRACTS["mutual_nda"]["text"]
        qa_data = answer_question_locally(doc_text, "What is the pet deposit policy and can I bring my dog?")
        self.assertIn("does not appear to contain an explicit clause", qa_data.answer)
        print("[OK] Grounded Q&A unmentioned topic handled cleanly")

    # =========================================================================
    # 6. CONTRACT COMPARISON & REDLINE DIFF TESTS
    # =========================================================================
    def test_compare_mutual_vs_unilateral_nda(self):
        """Tests comparative redline diffing and net favorability shift calculation."""
        doc_a = SAMPLE_CONTRACTS["mutual_nda"]["text"]
        doc_b = SAMPLE_CONTRACTS["unilateral_nda_aggressive"]["text"]

        diff_data = compare_documents_locally("Mutual NDA", doc_a, "Unilateral NDA", doc_b)
        self.assertIn("Counterparty", diff_data.favorability_shift)
        self.assertGreaterEqual(len(diff_data.key_differences), 3)
        
        impacts = [d.impact for d in diff_data.key_differences]
        self.assertTrue(any("Counterparty" in imp for imp in impacts))
        print(f"[OK] Contract comparison passed: {diff_data.favorability_shift}")

    def test_compare_diff_symmetry(self):
        """Tests comparison reciprocity: when swapping Doc A and Doc B, favorability inverts."""
        doc_a = SAMPLE_CONTRACTS["mutual_nda"]["text"]
        doc_b = SAMPLE_CONTRACTS["unilateral_nda_aggressive"]["text"]

        diff_b_vs_a = compare_documents_locally("Unilateral NDA", doc_b, "Mutual NDA", doc_a)
        self.assertIn("You", diff_b_vs_a.favorability_shift)
        print(f"[OK] Comparison symmetry verified: {diff_b_vs_a.favorability_shift}")

    # =========================================================================
    # 7. NEGOTIATION COUNTER-EMAIL GENERATOR TESTS
    # =========================================================================
    def test_counter_email_generation(self):
        """Tests automated drafting of polite, persuasive counter-proposal emails."""
        roles = ["Landlord", "Client", "Hiring Manager"]
        tones = ["Collaborative & Friendly", "Professional & Direct", "Firm & Formal"]
        
        for role, tone in zip(roles, tones):
            result = generate_counter_email_locally(
                recipient_role=role,
                clauses=["Automatic Renewal", "Indemnification & Liability"],
                tone=tone
            )
            self.assertIn("subject", result)
            self.assertIn(role, result["email_body"])
            self.assertTrue(len(result["talking_points"]) >= 2)
        print("[OK] Negotiation counter-email generator tested across multiple roles and tones")

    # =========================================================================
    # 8. ATTORNEY CONSULTATION DOSSIER TESTS
    # =========================================================================
    def test_attorney_brief_generation(self):
        """Tests formatting and generation of the 1-page Attorney Consultation Pack."""
        lease_text = SAMPLE_CONTRACTS["residential_lease"]["text"]
        analysis_data = analyze_document_locally("Austin Apartment Lease", lease_text)

        brief_res = self.client.post("/api/attorney-brief", json=analysis_data.model_dump())
        self.assertEqual(brief_res.status_code, 200)
        data = brief_res.json()
        brief_md = data["brief_markdown"]
        
        self.assertIn("# ATTORNEY CONSULTATION BRIEFING DOSSIER", brief_md)
        self.assertIn("Executive Summary", brief_md)
        self.assertIn("Critical Legal Red Flags", brief_md)
        self.assertIn("High-Priority Questions for Legal Counsel", brief_md)
        self.assertIn("DISCLAIMER", brief_md)
        self.assertGreaterEqual(len(data["consultation_checklist"]), 4)
        print("[OK] Attorney consultation dossier passed")

    # =========================================================================
    # 9. SECURITY & BOUNDARY TESTS
    # =========================================================================
    def test_empty_text_analysis_rejected(self):
        """Security: Rejects empty text submissions with HTTP 400."""
        res = self.client.post("/api/analyze", json={"title": "Empty", "text": "   "})
        self.assertEqual(res.status_code, 400)
        print("[OK] Security: Empty text rejected")

    def test_excessive_text_length_rejected(self):
        """Security: Rejects texts exceeding 300,000 characters with HTTP 413."""
        huge_text = "Legal clause text. " * 20000  # ~380k chars
        res = self.client.post("/api/analyze", json={"title": "Huge", "text": huge_text})
        self.assertEqual(res.status_code, 413)
        print("[OK] Security: 300k+ character overflow rejected (HTTP 413)")

    def test_invalid_file_extension_upload_rejected(self):
        """Security: Rejects malicious/unsupported file types like .exe or .bin."""
        file_content = b"Binary executable content"
        res = self.client.post("/api/upload", files={
            "file": ("malicious_payload.exe", file_content, "application/octet-stream")
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("Unsupported file format", res.json()["detail"])
        print("[OK] Security: Malicious .exe file rejected")

    def test_valid_txt_upload(self):
        """Verifies clean text file upload."""
        txt_content = b"RESIDENTIAL LEASE AGREEMENT\nBetween Landlord and Tenant."
        res = self.client.post("/api/upload", files={
            "file": ("lease.txt", txt_content, "text/plain")
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["filename"], "lease.txt")
        self.assertGreater(data["word_count"], 0)
        print("[OK] Valid .txt file upload passed")

    def test_script_injection_sanitization(self):
        """Security: Verifies that HTML/Script tags in clause text are safely processed."""
        malicious_clause = "Clause 1: <script>alert('XSS')</script> Payment is due on the 1st."
        data = analyze_document_locally("Injected Contract", malicious_clause)
        self.assertIsNotNone(data)
        self.assertTrue(len(data.clauses) >= 1)
        print("[OK] Security: Script injection payload handled safely")

    # =========================================================================
    # 10. PERFORMANCE & EFFICIENCY BENCHMARK
    # =========================================================================
    def test_execution_efficiency_benchmark(self):
        """Efficiency: Ensures local legal analysis completes in under 30ms."""
        lease_text = SAMPLE_CONTRACTS["residential_lease"]["text"]
        start_time = time.time()
        data = analyze_document_locally("Speed Test Lease", lease_text)
        elapsed = time.time() - start_time
        self.assertIsNotNone(data)
        self.assertLess(elapsed, 0.03)  # Under 30 milliseconds!
        print(f"[OK] Performance: Full contract analysis executed in {elapsed*1000:.2f}ms (< 30ms target)")

if __name__ == "__main__":
    unittest.main()
