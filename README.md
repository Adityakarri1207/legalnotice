# ⚖️ JurisClear AI — GenAI Legal Intelligence & Accessibility Platform

> **Democratizing legal comprehension, uncovering hidden risks, comparing agreements, and empowering people to navigate contracts with clarity and confidence.**
>
> *Powered by Google Gemini 3.8 Flash (`gemini-3.8-flash`) and the JurisClear Legal Intelligence Engine.*

---

## 🌟 Executive Summary

Legal contracts, lease agreements, service master agreements (MSAs), non-disclosure agreements (NDAs), and employment offer letters are notoriously dense, archaic, and skewed in favor of corporate drafters. For ordinary individuals, renters, freelance developers, and small business owners, hiring an attorney for every standard document is financially prohibitive—yet signing blind leads to severe traps: **forfeited security deposits, unlimited personal liabilities, perpetual non-competes, and intellectual property forfeiture**.

**JurisClear AI** bridges this divide. It is a full-stack, GenAI-powered legal intelligence copilot engineered to:
1. **Translate convoluted legalese** into plain, human-friendly English across 3 customizable comprehension tiers.
2. **Expose predatory "Gotcha" clauses** using a calibrated Risk Radar scoring system (0–100).
3. **Semantically redline & compare** contracts (e.g. Standard vs. Landlord/Vendor revised terms) with net favorability shift indicators.
4. **Answer questions with direct verbatim clause citations** and simulate real-world "What-If" scenarios.
5. **Draft counter-proposals and emails** to negotiate fairer terms with counter-parties.
6. **Generate a 1-page structured Attorney Consultation Dossier** designed to save billable hours when legal counsel is required.

---

## 🚀 Key Modules & Capabilities

### 1. 📖 Synchronized Clause Simplifier ("Legalese to Human")
- **Multi-Level Comprehension Tiers**:
  - 👶 **ELI5 / Everyday Human**: Plain analogies, 6th-grade readability, zero jargon.
  - ⚖️ **Balanced / Practical**: Concrete everyday takeaways, required actions, notice windows.
  - 💼 **Strategic / Business**: Commercial exposure, financial downside, leverage points.
- **Synchronized Split-Screen View**: Click any clause in the contract to instantly focus and cross-highlight its plain-English interpretation.

### 2. 🚨 Risk Radar & "Gotcha" Trap Detection
- Categorizes provisions by severity: **Critical Risk 🔴**, **Caution / Warning 🟡**, and **Fair / Safe 🟢**.
- Automatically spots notorious legal traps:
  - *Hidden 60-day auto-renewals with security deposit forfeiture*
  - *24/7 unannounced landlord entry rights*
  - *Unlimited personal indemnification without liability caps*
  - *Sweeping IP grabs capturing weekend off-hours side projects*
  - *Worldwide 24-month non-competes and moonlighting bans*
  - *Disproportionate liquidated damage fines ($250,000 penalties)*
  - *One-sided fee shifting forcing you to pay the landlord's lawyers even if you win!*
- **Actionable Benchmarks**: For every red flag, JurisClear shows what **Standard Industry Practice** is and provides **Ready-to-Use Counter-Language** you can copy with one click.

### 3. ⚖️ Smart Contract Diff & Redline Comparator
- Compares two versions of an agreement (e.g. Version 1 vs Version 2, Standard Mutual NDA vs Vendor Unilateral NDA, or Offer Letter A vs Offer B).
- Calculates:
  - **Net Favorability Shift**: e.g., *"Shifted 65% towards Counterparty (Significantly more restrictive)"*.
  - **Risk Delta**: Identifies which party gained unilateral advantages.
  - **Side-by-Side Semantic Diff**: Highlights additions (green), omissions (red), and modified risk categories.

### 4. 💬 Grounded Q&A with Verbatim Clause Citations
- Interactive natural language Q&A grounded strictly in the document text.
- Every response provides:
  - Direct Plain-English Answer.
  - Verbatim Clause Citation with Section title and quote.
  - Practical Takeaway bullet point.
- **Built-in "What-If" Scenario Explorer**:
  - *"What if I pay rent 3 days late?"*
  - *"What if I terminate or move out early?"*
  - *"Can they change terms without asking me?"*
  - *"Do they own my weekend side projects?"*

### 5. 📅 Obligations Matrix & Action Playbook
- **Notice & Milestone Timeline**: Extracts all timeframes (60 days notice, Net-90, 15 business days) into a chronological schedule.
- **Pre-Signature Diligence Checklist**: Interactive checklist with strike-through progress tracking.
- **Negotiation Counter-Email Drafter**:
  - Select which clauses you want to negotiate.
  - Select your desired tone (*Collaborative & Friendly*, *Professional & Direct*, or *Firm*).
  - One-click generates a ready-to-send email proposing fair compromises.

### 6. 💼 Attorney Consultation Dossier ("Save Billable Hours")
- Compiles an executive legal brief for an attorney consultation.
- Includes document summary, identified contracting entities, top red flags, and **5 targeted high-yield questions for counsel**.
- Exportable to Markdown or 1-click **Print / Save as PDF**.

---

## 🛡️ Ethical & Legal Compliance Guardrails

JurisClear AI adheres strictly to legal ethics requirements:
- **Informational Assistance, Not Legal Advice**: Transparent banners, headers, and dossier footers emphasize that JurisClear assists in understanding and preparation, but never replaces licensed legal counsel.
- **Verifiable Grounding**: Every analysis links back to verbatim excerpts from the source document to prevent AI hallucinations.
- **Privacy First**: Documents are processed in-memory and never stored on public servers or used for public model training.

---

## ⚡ Instant Test Drives (Pre-Loaded Samples)

JurisClear AI includes 5 pre-loaded realistic contracts for instantaneous testing:
1. 🏠 **Austin Apartment Lease (Predatory Traps)**: 60-day auto-renewal forfeiture, unilateral 24/7 entry, $550 mandatory cleaning fee deductions.
2. 💻 **Freelance Software Dev Contract (IP Grab & Unlimited Liability)**: Off-hours IP capture, uncapped liability, Net-90 payment terms.
3. 🤝 **Mutual NDA (Balanced Standard)**: Reciprocal 2-year confidentiality terms, standard trade secret carve-outs.
4. ⚠️ **Aggressive Vendor NDA (Perpetual $250k Penalty)**: Unilateral secrecy in perpetuity, $250,000 liquidated damages, 3-year non-solicit.
5. 👔 **Executive Employment Offer**: 24-month bonus clawback, broad moonlighting ban, mandatory arbitration.

---

## 🛠️ Architecture & Tech Stack

```
JurisClear AI/
├── app/
│   ├── main.py              # FastAPI server, REST API endpoints & static asset serving
│   ├── gemini_service.py    # Google GenAI SDK integration with Gemini 3.8 Flash
│   ├── analyzer.py          # AST/heuristic legal intelligence engine (zero-key fallback)
│   ├── models.py            # Pydantic data schemas
│   └── sample_contracts.py  # Realistic legal contract library
├── static/
│   ├── index.html           # Modern glassmorphism UI & multi-tab workspace
│   ├── styles.css           # Responsive design system & risk color palettes
│   └── app.js               # Reactive vanilla JavaScript frontend logic
├── tests/
│   └── test_api.py          # Comprehensive integration test suite (100% pass)
├── run.bat                  # One-click Windows launcher
└── README.md                # Documentation & architecture guide
```

- **Backend**: Python 3.12, FastAPI, Uvicorn, Pydantic, PyPDF, Python-Docx, Google GenAI SDK (`google-genai`).
- **AI Models**:
  - `gemini-3.8-flash` (Primary multimodal & reasoning model)
  - `JurisClear Built-in Legal Intelligence Engine` (High-precision AST/regex parser for offline and immediate zero-setup execution)
- **Frontend**: Responsive Single Page App (SPA) built with semantic HTML5, modern CSS3 variables, and vanilla ES6+ (no complex npm builds required).

---

## 🌐 1-Click Cloud Deployment

Deploy JurisClear AI with a single click to free cloud platforms:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Adityakarri1207/legalnotice)

### Instant Cloud Hosting Steps:
1. **Render.com (Free Tier)**:
   - Click the **Deploy to Render** button above or visit [Render New Web Service](https://dashboard.render.com/web/new).
   - Connect the repository: `https://github.com/Adityakarri1207/legalnotice`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - *(Optional)* Add Environment Variable: `GEMINI_API_KEY` with your Gemini key.
   - Click **Create Web Service** — Render deploys your live HTTPS link in under 2 minutes!

2. **Railway / Koyeb / Fly.io / Docker**:
   - The repository includes a production-ready `Dockerfile` and `Procfile`. Simply link the GitHub repository to Railway or Koyeb and it will deploy automatically.

---

## 🏃 Quickstart Guide (Local)

### Option 1: One-Click Launcher (Windows)
Double-click `run.bat` or run:
```powershell
.\run.bat
```
This automatically starts the server at `http://localhost:8000` and opens your browser.

### Option 2: Command Line
```powershell
# Activate virtual environment
.\.venv\Scripts\activate

# Start the server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Navigate to `http://localhost:8000`.

---

## 🧪 Running Automated Tests

Run the integration test suite:
```powershell
.\.venv\Scripts\python.exe -m unittest tests/test_api.py
```
**Test Coverage**:
- Health check & metadata validation
- Sample contracts retrieval
- Single-document deep legal analysis & risk scoring
- Grounded Q&A with clause citations
- Contract diffing & favorability shift calculation
- Attorney consultation dossier generation
- Counter-proposal email drafting

---

## 💡 Gemini API Key Configuration

JurisClear AI works **out-of-the-box** using its built-in legal intelligence engine. To enable **Gemini 3.8 Flash**:
1. Click **⚙️ Settings** in the top navigation bar.
2. Paste your Google Gemini API key.
3. Click **Save & Apply** (stored securely in browser `localStorage`).
Alternatively, set the environment variable:
```powershell
$env:GEMINI_API_KEY="your-gemini-api-key"
```
