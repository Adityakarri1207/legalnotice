// JurisClear AI — Frontend Reactive Application

let state = {
  currentDocAnalysis: null,
  currentDocText: "",
  currentDocTitle: "Legal Document",
  readingLevel: "eli5", // "eli5", "practical", "business"
  simplifierView: "split", // "split" or "flip"
  selectedCategory: "all",
  searchQuery: "",
  activeMode: "single",
  activeInputTab: "upload",
  apiKey: localStorage.getItem("jurisclear_gemini_api_key") || "",
  uploadedDocId: null,
  currentDiffData: null,
  diffSubView: "all",
  redlineDisplayMode: "inline",
  docAName: "Document A",
  docBName: "Document B"
};

// Initialization on DOM load
document.addEventListener("DOMContentLoaded", () => {
  checkBackendHealth();
  setupDropzone();
  setupTextListeners();
  
  if (state.apiKey) {
    document.getElementById("geminiApiKeyInput").value = state.apiKey;
    updateEngineBadge("⚡ Gemini 3.8 Flash Active");
  }
});

// Toast notification system
function showToast(message, type = "success") {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✅' : 'ℹ️'}</span> <span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px) scale(0.9)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

// Check backend status and engine availability
async function checkBackendHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.gemini_env_key_configured || state.apiKey) {
      updateEngineBadge("⚡ Gemini Active");
    } else {
      updateEngineBadge("🛡️ Built-in Engine Ready");
    }
  } catch (err) {
    console.warn("Backend health check failed:", err);
  }
}

function updateEngineBadge(text) {
  const badge = document.getElementById("engineBadge");
  if (badge) badge.textContent = text;
}

// Mode Switcher (Single vs Compare)
function switchMode(mode) {
  state.activeMode = mode;
  document.getElementById("modeSingleBtn").classList.toggle("active", mode === "single");
  document.getElementById("modeCompareBtn").classList.toggle("active", mode === "compare");
  document.getElementById("singleIntakeMode").style.display = mode === "single" ? "block" : "none";
  document.getElementById("compareIntakeMode").style.display = mode === "compare" ? "block" : "none";
}

// Input tab switcher (Upload vs Paste)
function switchInputTab(tab) {
  state.activeInputTab = tab;
  document.getElementById("tabUploadBtn").classList.toggle("active", tab === "upload");
  document.getElementById("tabPasteBtn").classList.toggle("active", tab === "paste");
  document.getElementById("uploadView").style.display = tab === "upload" ? "block" : "none";
  document.getElementById("pasteView").style.display = tab === "paste" ? "block" : "none";
}

// Textarea listeners
function setupTextListeners() {
  const pasteArea = document.getElementById("pasteDocText");
  pasteArea.addEventListener("input", () => {
    const text = pasteArea.value;
    document.getElementById("charCount").textContent = `${text.length.toLocaleString()} characters`;
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;
    document.getElementById("wordCount").textContent = `${words.toLocaleString()} words`;
  });
}

// Drag & drop file setup
function setupDropzone() {
  const dropzone = document.getElementById("dropzone");
  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    }, false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length) uploadFile(files[0]);
  }, false);
}

function handleFileSelect(event) {
  const file = event.target.files[0];
  if (file) uploadFile(file);
}

// File Upload API call
async function uploadFile(file) {
  const statusDiv = document.getElementById("fileUploadStatus");
  statusDiv.style.display = "block";
  statusDiv.innerHTML = `<span>⏳ Uploading and extracting text from <strong>${file.name}</strong>...</span>`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload failed");
    }

    const data = await res.json();
    state.uploadedDocId = data.document_id;
    state.currentDocTitle = file.name.replace(/\.[^/.]+$/, "");
    
    // Switch to paste view with populated content
    document.getElementById("pasteDocTitle").value = state.currentDocTitle;
    document.getElementById("pasteDocText").value = data.text_preview;
    document.getElementById("pasteDocText").dispatchEvent(new Event("input"));
    
    statusDiv.innerHTML = `<span>✅ Extracted <strong>${data.word_count.toLocaleString()} words</strong> from <strong>${data.filename}</strong>!</span>`;
    showToast(`Loaded ${data.filename} (${data.word_count} words)`, "success");
    
    // Auto start analysis
    startAnalysis();
  } catch (err) {
    statusDiv.innerHTML = `<span style="color: var(--risk-critical);">❌ Error: ${err.message}</span>`;
    showToast(`Error: ${err.message}`, "warning");
  }
}

// Load pre-built realistic sample contracts
async function loadSample(sampleId) {
  try {
    const res = await fetch(`/api/samples/${sampleId}`);
    if (!res.ok) throw new Error("Could not load sample");
    const data = await res.json();

    switchMode("single");
    switchInputTab("paste");

    document.getElementById("pasteDocTitle").value = data.title;
    document.getElementById("pasteDocText").value = data.text;
    document.getElementById("pasteDocText").dispatchEvent(new Event("input"));

    showToast(`Loaded "${data.title}"`, "success");
    startAnalysis();
  } catch (err) {
    alert("Failed to load sample: " + err.message);
  }
}

// 1-Click Load for Diff Comparison
async function loadCompareDemo() {
  try {
    const [resA, resB] = await Promise.all([
      fetch("/api/samples/mutual_nda"),
      fetch("/api/samples/unilateral_nda_aggressive")
    ]);
    const [docA, docB] = await Promise.all([resA.json(), resB.json()]);

    document.getElementById("docAName").value = "Document A: Balanced Mutual NDA";
    document.getElementById("docAText").value = docA.text;

    document.getElementById("docBName").value = "Document B: Unilateral Aggressive NDA";
    document.getElementById("docBText").value = docB.text;

    showToast("Loaded Mutual vs Aggressive NDA for comparison", "success");
    startComparison();
  } catch (err) {
    alert("Failed to load compare demo: " + err.message);
  }
}

// Start Document Analysis
async function startAnalysis() {
  let title = document.getElementById("pasteDocTitle").value.trim();
  let text = document.getElementById("pasteDocText").value.trim();

  if (!text) {
    alert("Please upload a file or paste contract text before analyzing.");
    return;
  }

  if (!title) title = "Analyzed Legal Contract";
  state.currentDocTitle = title;
  state.currentDocText = text;

  const btn = document.getElementById("btnAnalyze");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> <span>Analyzing Legalese & Risks...</span>`;

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: title,
        text: text,
        api_key: state.apiKey || undefined
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Analysis failed");
    }

    const data = await res.json();
    state.currentDocAnalysis = data;

    // Show results section immediately so layout is visible
    const resultsSection = document.getElementById("resultsSection");
    if (resultsSection) {
      resultsSection.style.display = "block";
    }
    const singleCard = document.getElementById("singleOverviewCard");
    if (singleCard) singleCard.style.display = "grid";
    const compareCard = document.getElementById("compareOverviewCard");
    if (compareCard) compareCard.style.display = "none";

    renderAnalysisResults(data);
    generateAttorneyDossier(data);

    if (resultsSection) {
      resultsSection.scrollIntoView({ behavior: "smooth" });
    }
    showToast("Contract analysis complete!", "success");

  } catch (err) {
    console.error("Analysis Error:", err);
    alert("Analysis Error: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>🚀 Run Deep Legal Analysis</span>`;
  }
}

// Render Analysis Dashboard
function renderAnalysisResults(data) {
  // Top Banner
  document.getElementById("resDocTitle").textContent = data.filename || "Legal Document";
  document.getElementById("resDocType").textContent = data.document_type || "Contract";
  document.getElementById("resEngineTag").textContent = `Powered by ${data.ai_engine_used || "JurisClear AI"}`;
  document.getElementById("resReadabilityTag").textContent = data.readability_summary || "Grade 6 Readability";
  document.getElementById("resExecSummary").textContent = data.executive_summary || "Analysis completed.";

  let partiesText = "Identified Parties";
  if (Array.isArray(data.key_parties) && data.key_parties.length > 0) {
    partiesText = data.key_parties.join(" & ");
  } else if (typeof data.key_parties === "string") {
    partiesText = data.key_parties;
  }
  document.getElementById("resParties").textContent = partiesText;

  document.getElementById("resGovLaw").textContent = data.governing_law || "Applicable Law";

  let finText = "Standard";
  if (Array.isArray(data.financial_commitments) && data.financial_commitments.length > 0) {
    finText = data.financial_commitments.slice(0, 2).join(", ");
  } else if (typeof data.financial_commitments === "string") {
    finText = data.financial_commitments;
  }
  document.getElementById("resFinancials").textContent = finText;

  // Animated Radial SVG Risk Meter
  animateRiskMeter(data.overall_risk_score || 0, data.overall_risk_label || "Evaluated Risk");

  document.getElementById("statRedFlags").textContent = `${data.red_flags_count || 0} Red Flags`;
  document.getElementById("statWarningFlags").textContent = `${data.warning_flags_count || 0} Warnings`;
  document.getElementById("statSafeFlags").textContent = `${data.safe_flags_count || 0} Safe`;
  document.getElementById("tabRiskCount").textContent = (data.red_flags_count || 0) + (data.warning_flags_count || 0);

  // Category filters
  renderCategoryFilters(data.category_counts || {});

  // Render Tabs defensively
  try { renderSimplifierClauses(data.clauses || []); } catch (e) { console.error("renderSimplifierClauses error:", e); }
  try { render3DFlipCards(data.clauses || []); } catch (e) { console.error("render3DFlipCards error:", e); }
  try { renderRiskRadar(data.clauses || []); } catch (e) { console.error("renderRiskRadar error:", e); }
  try { renderSuggestedQuestions(data.suggested_user_questions || []); } catch (e) { console.error("renderSuggestedQuestions error:", e); }
  try { renderPlaybook(data.deadlines_and_obligations || [], data.presignature_checklist || [], data.clauses || []); } catch (e) { console.error("renderPlaybook error:", e); }
}

// Animate SVG Radial Risk Meter
function animateRiskMeter(score, label) {
  const scoreNum = document.getElementById("riskScoreNum");
  const scoreLabel = document.getElementById("riskLabel");
  const circle = document.getElementById("riskCircleProgress");

  if (scoreNum) scoreNum.textContent = score;
  if (scoreLabel) scoreLabel.textContent = label;

  let scoreColor = "var(--risk-safe)";
  if (score >= 70) scoreColor = "var(--risk-critical)";
  else if (score >= 40) scoreColor = "var(--risk-warning)";
  
  if (scoreNum) scoreNum.style.color = scoreColor;
  if (scoreLabel) scoreLabel.style.color = scoreColor;

  if (circle) {
    try {
      const radius = circle.r.baseVal ? circle.r.baseVal.value : 50;
      const circumference = 2 * Math.PI * radius; // ~314.159
      const offset = circumference - (score / 100) * circumference;
      circle.style.stroke = scoreColor;
      circle.style.strokeDasharray = `${circumference}`;
      circle.style.strokeDashoffset = `${offset}`;
    } catch (e) {
      console.warn("Could not animate circle SVG:", e);
    }
  }
}

// Category filter rendering
function renderCategoryFilters(categoryCounts) {
  const container = document.getElementById("clauseCategoryFilters");
  if (!container) return;
  container.innerHTML = "";

  const allChip = document.createElement("button");
  allChip.className = "filter-chip active";
  allChip.textContent = "All Categories";
  allChip.onclick = () => filterByCategory("all");
  container.appendChild(allChip);

  if (categoryCounts) {
    for (const [cat, count] of Object.entries(categoryCounts)) {
      const chip = document.createElement("button");
      chip.className = "filter-chip";
      chip.textContent = `${cat} (${count})`;
      chip.onclick = () => filterByCategory(cat);
      container.appendChild(chip);
    }
  }
}

function filterByCategory(category) {
  state.selectedCategory = category;
  document.querySelectorAll("#clauseCategoryFilters .filter-chip").forEach(c => {
    c.classList.toggle("active", c.textContent.startsWith(category === "all" ? "All" : category));
  });
  applyClauseFilters();
}

function handleClauseSearch() {
  state.searchQuery = document.getElementById("clauseSearchInput").value.toLowerCase().trim();
  applyClauseFilters();
}

function applyClauseFilters() {
  if (!state.currentDocAnalysis) return;
  const filtered = state.currentDocAnalysis.clauses.filter(c => {
    const matchesCat = state.selectedCategory === "all" || c.risk_category === state.selectedCategory;
    const matchesSearch = !state.searchQuery || 
      c.section_title.toLowerCase().includes(state.searchQuery) ||
      c.original_text.toLowerCase().includes(state.searchQuery) ||
      c.simplified_eli5.toLowerCase().includes(state.searchQuery);
    return matchesCat && matchesSearch;
  });

  renderSimplifierClauses(filtered);
  render3DFlipCards(filtered);
}

// Switch between Split Screen and 3D Flip Card View
function switchSimplifierView(mode) {
  state.simplifierView = mode;
  document.getElementById("viewSplitBtn").classList.toggle("active", mode === "split");
  document.getElementById("viewFlipBtn").classList.toggle("active", mode === "flip");
  document.getElementById("splitViewContainer").style.display = mode === "split" ? "grid" : "none";
  document.getElementById("flipCardsContainer").style.display = mode === "flip" ? "grid" : "none";
}

// TAB 1: Split View Clauses
function renderSimplifierClauses(clauses) {
  document.getElementById("clauseCountBadge").textContent = `${clauses.length} clauses displayed`;
  const originalList = document.getElementById("originalClausesList");
  const simplifiedList = document.getElementById("simplifiedClausesList");

  originalList.innerHTML = "";
  simplifiedList.innerHTML = "";

  clauses.forEach((c) => {
    // Left card (Original text)
    const origCard = document.createElement("div");
    origCard.className = `clause-card ${c.risk_level}-glow`;
    origCard.id = `orig-${c.id}`;
    origCard.innerHTML = `
      <div class="clause-top">
        <span class="clause-title">${escapeHtml(c.section_title)}</span>
        <span class="risk-pill ${getRiskPillClass(c.risk_level)}">${c.risk_level.toUpperCase()}</span>
      </div>
      <div class="clause-body">${escapeHtml(c.original_text)}</div>
      <div style="margin-top: 0.6rem; display: flex; justify-content: space-between; align-items: center; font-size: 0.78rem; color: var(--text-muted);">
        <span>Category: <strong>${c.risk_category}</strong></span>
        <span>Leverage: <strong>${c.negotiation_leverage || 'Standard'}</strong></span>
      </div>
    `;

    // Right card (Simplified text)
    const simpCard = document.createElement("div");
    simpCard.className = "clause-card simplified-card";
    simpCard.id = `simp-${c.id}`;
    simpCard.innerHTML = `
      <div class="clause-top">
        <span class="clause-title" style="color: var(--primary);">Plain-English Interpretation</span>
        <span class="detail-label">${c.risk_category}</span>
      </div>
      <div class="clause-body" id="text-simp-${c.id}">
        ${getClauseTextForLevel(c, state.readingLevel)}
      </div>
    `;

    // Interactive synchronized hover/focus
    origCard.addEventListener("click", () => focusClausePair(c.id));
    simpCard.addEventListener("click", () => focusClausePair(c.id));

    originalList.appendChild(origCard);
    simplifiedList.appendChild(simpCard);
  });
}

// TAB 1 (Mode B): 3D Flip Cards View
function render3DFlipCards(clauses) {
  const container = document.getElementById("flipCardsContainer");
  if (!container) return;
  container.innerHTML = "";

  clauses.forEach(c => {
    const wrapper = document.createElement("div");
    wrapper.className = "card-3d-wrapper";

    const card = document.createElement("div");
    card.className = "card-3d";
    card.id = `flipcard-${c.id}`;

    // Click anywhere on card (except buttons / links / inputs) to flip
    card.addEventListener("click", (e) => {
      if (e.target.closest("button, a, input, textarea, select, .no-flip")) {
        return;
      }
      toggleCardFlip(c.id, e);
    });

    // Front Face (Original Contract Clause)
    const front = document.createElement("div");
    front.className = `card-face card-face-front ${c.risk_level}`;
    front.innerHTML = `
      <div>
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.6rem; gap: 0.5rem;">
          <span style="font-weight: 800; font-size: 1.05rem; color: var(--secondary); line-height: 1.35;">${escapeHtml(c.section_title)}</span>
          <span class="risk-pill ${getRiskPillClass(c.risk_level)}">${c.risk_level.toUpperCase()}</span>
        </div>
        <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.75rem;">
          Category: <strong>${c.risk_category}</strong> &bull; Leverage: <strong>${c.negotiation_leverage || 'Standard'}</strong>
        </div>
        <div style="font-size: 0.88rem; color: var(--text-secondary); line-height: 1.6; max-height: 180px; overflow-y: auto; padding-right: 0.25rem;">
          ${escapeHtml(c.original_text)}
        </div>
      </div>
      <div>
        <div class="card-flip-hint">
          <span class="card-flip-hint-badge">💡 Click card anywhere to flip</span>
          <button class="card-flip-btn" onclick="toggleCardFlip('${c.id}', event)">
            <span>🔄 Flip to Plain English</span>
          </button>
        </div>
      </div>
    `;

    // Back Face (Plain English Interpretation)
    const back = document.createElement("div");
    back.className = "card-face card-face-back";
    back.innerHTML = `
      <div>
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.6rem; gap: 0.5rem;">
          <span style="font-weight: 800; font-size: 1.05rem; color: #7c3aed; line-height: 1.35;">Plain-English Breakdown</span>
          <span class="badge" style="background: #f5f3ff; color: #7c3aed; border: 1px solid #ddd6fe;">${c.plain_english_score || 'Grade 6'}</span>
        </div>
        <div style="font-size: 0.9rem; color: var(--text-primary); line-height: 1.6; margin-bottom: 0.75rem; max-height: 180px; overflow-y: auto; padding-right: 0.25rem;">
          ${getClauseTextForLevel(c, state.readingLevel)}
        </div>
        <div style="padding: 0.6rem 0.8rem; background: rgba(255, 255, 255, 0.95); border-radius: 8px; border: 1px solid #e2e8f0; font-size: 0.82rem; margin-bottom: 0.4rem;">
          <strong>Negotiation Leverage:</strong> ${c.negotiation_leverage || 'Standard'}
        </div>
      </div>
      <div>
        <div class="card-flip-hint">
          <span class="card-flip-hint-badge">💡 Click card anywhere to flip</span>
          <button class="card-flip-btn" onclick="toggleCardFlip('${c.id}', event)">
            <span>🔄 Flip to Contract Text</span>
          </button>
        </div>
      </div>
    `;

    card.appendChild(front);
    card.appendChild(back);
    wrapper.appendChild(card);
    container.appendChild(wrapper);
  });
}

function toggleCardFlip(clauseId, event) {
  if (event) {
    event.stopPropagation();
  }
  const card = document.getElementById(`flipcard-${clauseId}`);
  if (card) {
    card.classList.toggle("is-flipped");
  }
}

function focusClausePair(clauseId) {
  document.querySelectorAll(".clause-card").forEach(el => el.classList.remove("focused"));
  const o = document.getElementById(`orig-${clauseId}`);
  const s = document.getElementById(`simp-${clauseId}`);
  if (o) o.classList.add("focused");
  if (s) {
    s.classList.add("focused");
    s.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function getRiskPillClass(level) {
  switch (level.toLowerCase()) {
    case "critical": return "pill-critical";
    case "warning": return "pill-warning";
    default: return "pill-safe";
  }
}

function getClauseTextForLevel(clause, level) {
  switch (level) {
    case "practical": return `<strong>Action Item:</strong> ${escapeHtml(clause.simplified_practical)}`;
    case "business": return `<strong>Commercial Exposure:</strong> ${escapeHtml(clause.simplified_business)}`;
    case "eli5":
    default:
      return `<strong>In Simple Terms:</strong> ${escapeHtml(clause.simplified_eli5)}`;
  }
}

function setReadingLevel(level) {
  state.readingLevel = level;
  document.getElementById("lvlEli5").classList.toggle("active", level === "eli5");
  document.getElementById("lvlPractical").classList.toggle("active", level === "practical");
  document.getElementById("lvlBusiness").classList.toggle("active", level === "business");

  const labelMap = {
    eli5: "Mode: ELI5 / Everyday Human",
    practical: "Mode: Balanced / Practical",
    business: "Mode: Strategic / Business"
  };
  document.getElementById("activeLevelLabel").textContent = labelMap[level];

  if (state.currentDocAnalysis) {
    state.currentDocAnalysis.clauses.forEach(c => {
      const el = document.getElementById(`text-simp-${c.id}`);
      if (el) el.innerHTML = getClauseTextForLevel(c, level);
    });
    render3DFlipCards(state.currentDocAnalysis.clauses);
  }
}

// TAB 2: Risk Radar Cards
function renderRiskRadar(clauses) {
  const container = document.getElementById("riskCardsContainer");
  container.innerHTML = "";

  clauses.forEach(c => {
    const card = document.createElement("div");
    card.className = `risk-card ${c.risk_level}`;
    card.setAttribute("data-risk-level", c.risk_level);

    let counterSection = "";
    if (c.recommended_counter_term) {
      counterSection = `
        <div class="benchmark-box counter-box">
          <div class="counter-header">
            <span>🛡️ Recommended Counter-Proposal Rider</span>
            <button class="btn-secondary" style="padding: 0.25rem 0.6rem; font-size: 0.78rem;" onclick="copyToClipboard('${escapeJsString(c.recommended_counter_term)}', 'Counter-proposal text copied!')">📋 Copy Rider</button>
          </div>
          <code style="display: block; white-space: pre-wrap; font-size: 0.85rem;">${escapeHtml(c.recommended_counter_term)}</code>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="risk-card-header">
        <div class="risk-title">
          <span>${c.risk_level === 'critical' ? '🚨' : c.risk_level === 'warning' ? '⚠️' : '✅'}</span>
          <span>${escapeHtml(c.section_title)}</span>
        </div>
        <span class="risk-pill ${getRiskPillClass(c.risk_level)}">${c.risk_level.toUpperCase()} [${c.risk_category}]</span>
      </div>
      <div class="risk-explanation">
        <strong>Why this is dangerous:</strong> ${escapeHtml(c.risk_explanation)}
      </div>
      <div class="risk-benchmarks">
        <div class="benchmark-box standard-box">
          <strong>Standard Industry Practice:</strong><br>
          ${escapeHtml(c.industry_standard)}
        </div>
        ${counterSection}
      </div>
    `;

    container.appendChild(card);
  });
}

function filterRisks(filter) {
  document.querySelectorAll("#pane-radar .filter-chip").forEach(b => b.classList.remove("active"));
  event.target.classList.add("active");

  const cards = document.querySelectorAll(".risk-card");
  cards.forEach(card => {
    const level = card.getAttribute("data-risk-level");
    if (filter === "all" || level === filter) {
      card.style.display = "block";
    } else {
      card.style.display = "none";
    }
  });
}

// TAB 3: Contract Diff / Redline
async function startComparison() {
  const docAName = document.getElementById("docAName").value.trim() || "Document A";
  const docAText = document.getElementById("docAText").value.trim();
  const docBName = document.getElementById("docBName").value.trim() || "Document B";
  const docBText = document.getElementById("docBText").value.trim();

  if (!docAText || !docBText) {
    alert("Please provide text for both Document A and Document B to compare.");
    return;
  }

  const btn = document.getElementById("btnRunCompare");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> <span>Calculating Semantic Redline, Similarities & Shifts...</span>`;

  try {
    const res = await fetch("/api/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        doc_a_name: docAName,
        doc_a_text: docAText,
        doc_b_name: docBName,
        doc_b_text: docBText,
        api_key: state.apiKey || undefined
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Comparison failed");
    }

    const data = await res.json();
    state.currentDiffData = data;
    state.docAName = docAName;
    state.docBName = docBName;

    renderDiffDashboard(data, docAName, docBName);

    // Switch view to compare overview & diff tab
    const singleCard = document.getElementById("singleOverviewCard");
    if (singleCard) singleCard.style.display = "none";

    const compCard = document.getElementById("compareOverviewCard");
    if (compCard) compCard.style.display = "block";

    const resultsSection = document.getElementById("resultsSection");
    if (resultsSection) resultsSection.style.display = "block";

    switchFeatureTab("diff");
    if (compCard) {
      compCard.scrollIntoView({ behavior: "smooth" });
    }
    showToast("Comparative Redline & Similarity Analysis Complete!", "success");

  } catch (err) {
    alert("Diff Error: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>⚖️ Compare Documents & Analyze Risk Shift</span>`;
  }
}

function renderDiffDashboard(data, nameA, nameB) {
  // 1. Dual Document Profiles
  if (data.doc_a_profile) {
    const pA = data.doc_a_profile;
    document.getElementById("profileDocAName").textContent = pA.name || nameA;
    document.getElementById("profileDocAType").textContent = pA.document_type || "Contract";
    document.getElementById("profileDocAClauses").textContent = `${pA.clause_count} clauses`;
    
    const scoreAEl = document.getElementById("profileDocAScore");
    scoreAEl.textContent = `Score: ${pA.risk_score}/100`;
    scoreAEl.className = `doc-profile-score ${pA.risk_score < 40 ? 'pill-safe' : (pA.risk_score < 70 ? 'pill-warning' : 'pill-critical')}`;
    document.getElementById("profileDocAPosture").textContent = pA.posture || "Standard";

    const highlightsA = document.getElementById("profileDocAHighlights");
    highlightsA.innerHTML = "";
    (pA.key_highlights || []).forEach(h => {
      const li = document.createElement("li");
      li.textContent = h;
      highlightsA.appendChild(li);
    });
  }

  if (data.doc_b_profile) {
    const pB = data.doc_b_profile;
    document.getElementById("profileDocBName").textContent = pB.name || nameB;
    document.getElementById("profileDocBType").textContent = pB.document_type || "Contract";
    document.getElementById("profileDocBClauses").textContent = `${pB.clause_count} clauses`;
    
    const scoreBEl = document.getElementById("profileDocBScore");
    scoreBEl.textContent = `Score: ${pB.risk_score}/100`;
    scoreBEl.className = `doc-profile-score ${pB.risk_score < 40 ? 'pill-safe' : (pB.risk_score < 70 ? 'pill-warning' : 'pill-critical')}`;
    document.getElementById("profileDocBPosture").textContent = pB.posture || "Standard";

    const highlightsB = document.getElementById("profileDocBHighlights");
    highlightsB.innerHTML = "";
    (pB.key_highlights || []).forEach(h => {
      const li = document.createElement("li");
      li.textContent = h;
      highlightsB.appendChild(li);
    });
  }

  // 2. Tug-of-War Balance Meter & Metrics
  const engTag = document.getElementById("compEngineTag");
  if (engTag) engTag.textContent = `Powered by ${data.ai_engine_used || "JurisClear AI"}`;

  const shiftBadge = document.getElementById("compareShiftBadge");
  shiftBadge.textContent = data.favorability_shift;
  if (data.favorability_shift.includes("Counterparty")) {
    shiftBadge.className = "risk-pill pill-critical";
  } else if (data.favorability_shift.includes("You")) {
    shiftBadge.className = "risk-pill pill-safe";
  } else {
    shiftBadge.className = "risk-pill pill-warning";
  }

  document.getElementById("compareRiskDeltaText").textContent = data.risk_delta;

  const pct = data.favorability_percentage !== undefined ? data.favorability_percentage : 0;
  // Left is You (0%), Center is 50%, Right is Counterparty (100%)
  const pointerPos = Math.min(Math.max(50 - (pct * 0.5), 10), 90);
  document.getElementById("balancePointer").style.left = `${pointerPos}%`;

  const totalDiffs = (data.differences && data.differences.length) || (data.key_differences && data.key_differences.length) || 0;
  const totalSims = (data.similarities && data.similarities.length) || 0;

  document.getElementById("compStatDiffs").textContent = `${totalDiffs} Key Differences`;
  document.getElementById("compStatSims").textContent = `${totalSims} Aligned Similarities`;
  document.getElementById("compStatAdded").textContent = `+${data.clauses_added_count || 0} Added Provisions`;
  document.getElementById("compStatRemoved").textContent = `-${data.clauses_removed_count || 0} Removed Provisions`;

  document.getElementById("compareRecommendationText").textContent = data.recommendation;

  // 3. Tab Count Badges
  document.getElementById("countDiffAll").textContent = totalDiffs;
  document.getElementById("countDiffSims").textContent = totalSims;
  const critCount = data.differences ? data.differences.filter(d => d.risk_severity === "critical").length : 0;
  document.getElementById("countDiffCritical").textContent = critCount;
  const playbookCount = (data.negotiation_checklist && data.negotiation_checklist.length) || 0;
  document.getElementById("countDiffPlaybook").textContent = playbookCount;
  document.getElementById("countDiffBadge").textContent = `${totalDiffs} Differences`;

  // 4. Render Similarities View
  renderSimilarities(data.similarities || [], nameA, nameB);

  // 5. Render Clause-by-Clause Differences View
  renderClauseDiffs(data.differences || [], data.key_differences || [], nameA, nameB);

  // 6. Render Negotiation Playbook Checklist
  renderDiffPlaybook(data.negotiation_checklist || []);
}

function renderSimilarities(similarities, nameA, nameB) {
  const container = document.getElementById("similaritiesGrid");
  container.innerHTML = "";

  if (!similarities || similarities.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; padding: 1.5rem; text-align: center; color: var(--text-muted); background: #f8fafc; border-radius: var(--radius-md);">No explicit shared provisions extracted between these documents.</div>`;
    return;
  }

  similarities.forEach(sim => {
    const card = document.createElement("div");
    card.className = "similarity-card";

    let quotesHtml = "";
    if (sim.doc_a_excerpt || sim.doc_b_excerpt) {
      quotesHtml = `
        <div class="similarity-quotes">
          ${sim.doc_a_excerpt ? `<div><strong style="color: #2563eb; font-size: 0.78rem;">${escapeHtml(nameA)}:</strong> <span style="font-style: italic;">"${escapeHtml(sim.doc_a_excerpt)}"</span></div>` : ''}
          ${sim.doc_b_excerpt ? `<div><strong style="color: #059669; font-size: 0.78rem;">${escapeHtml(nameB)}:</strong> <span style="font-style: italic;">"${escapeHtml(sim.doc_b_excerpt)}"</span></div>` : ''}
        </div>
      `;
    }

    card.innerHTML = `
      <div class="similarity-header">
        <span class="similarity-title">${escapeHtml(sim.title)}</span>
        <span class="badge" style="background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; font-size: 0.74rem;">${escapeHtml(sim.alignment_status || 'Aligned')}</span>
      </div>
      <div style="font-size: 0.78rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.35rem;">
        Category: ${escapeHtml(sim.category)}
      </div>
      <div class="similarity-desc">${escapeHtml(sim.description)}</div>
      ${quotesHtml}
    `;
    container.appendChild(card);
  });
}

function renderClauseDiffs(differences, fallbackDiffs, nameA, nameB) {
  const list = document.getElementById("diffItemsList");
  list.innerHTML = "";

  const items = differences.length > 0 ? differences : fallbackDiffs;

  if (!items || items.length === 0) {
    list.innerHTML = `<div style="padding: 1.5rem; text-align: center; color: var(--text-muted);">No significant clause divergences found.</div>`;
    return;
  }

  items.forEach(d => {
    const card = document.createElement("div");
    const changeType = d.change_type || 'modified';
    const severity = d.risk_severity || (d.impact && d.impact.includes("Counterparty") ? "critical" : "safe");
    card.className = `diff-item-card ${changeType} ${severity}-glow`;
    card.setAttribute("data-diff-severity", severity);

    let impactPill = "pill-warning";
    if (d.impact && d.impact.includes("Counterparty")) impactPill = "pill-critical";
    else if (d.impact && d.impact.includes("You")) impactPill = "pill-safe";

    const title = d.clause_title || d.category;
    const summary = d.summary;
    const advice = d.action_advice || "Review and negotiate this clause before signing.";
    const redline = d.redline_html;

    let contentHtml = "";
    if (state.redlineDisplayMode === 'side' || !redline) {
      // Side-by-side split view
      contentHtml = `
        <div class="diff-side-by-side-grid">
          <div class="diff-col-box col-a">
            <div style="font-weight: 800; font-size: 0.78rem; color: #2563eb; margin-bottom: 0.25rem;">${escapeHtml(nameA)} (${escapeHtml(d.doc_a_title || 'Original')})</div>
            <div>${escapeHtml(d.doc_a_excerpt || "Standard common-law / unaddressed")}</div>
          </div>
          <div class="diff-col-box col-b">
            <div style="font-weight: 800; font-size: 0.78rem; color: #ef4444; margin-bottom: 0.25rem;">${escapeHtml(nameB)} (${escapeHtml(d.doc_b_title || 'Proposed')})</div>
            <div style="font-weight: 600; color: #1e3a8a;">${escapeHtml(d.doc_b_excerpt || "Not specified")}</div>
          </div>
        </div>
      `;
    } else {
      // Inline redline markup view
      contentHtml = `
        <div class="redline-markup-box">
          <div style="font-size: 0.76rem; font-weight: 800; color: var(--text-muted); margin-bottom: 0.4rem; text-transform: uppercase;">Inline Redline (Word-for-Word Divergence):</div>
          <div>${d.redline_html}</div>
        </div>
      `;
    }

    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.6rem; flex-wrap: wrap; gap: 0.5rem;">
        <div>
          <span style="font-weight: 800; font-size: 1.1rem; color: var(--secondary);">${escapeHtml(title)}</span>
          <span class="detail-label" style="margin-left: 0.5rem;">[${escapeHtml(d.category)}]</span>
        </div>
        <div style="display: flex; gap: 0.4rem; align-items: center;">
          <span class="badge" style="text-transform: uppercase; font-size: 0.74rem;">${escapeHtml(changeType.replace('_', ' '))}</span>
          <span class="risk-pill ${impactPill}">${escapeHtml(d.impact)}</span>
        </div>
      </div>
      <div style="font-size: 0.94rem; color: var(--text-secondary); line-height: 1.55; margin-bottom: 0.75rem;">
        ${escapeHtml(summary)}
      </div>
      ${contentHtml}
      <div class="diff-advice-box">
        <strong>💡 Strategic Action:</strong> ${escapeHtml(advice)}
      </div>
    `;

    list.appendChild(card);
  });
}

function renderDiffPlaybook(checklist) {
  const container = document.getElementById("diffPlaybookChecklist");
  container.innerHTML = "";

  if (!checklist || checklist.length === 0) {
    container.innerHTML = `<div style="color: var(--text-muted);">No specific negotiation items generated. Both contracts appear relatively balanced.</div>`;
    return;
  }

  checklist.forEach((item, idx) => {
    const div = document.createElement("div");
    div.className = "playbook-step-card";
    div.innerHTML = `
      <input type="checkbox" id="diff-chk-${idx}" style="margin-top: 0.2rem; cursor: pointer;">
      <label for="diff-chk-${idx}" style="cursor: pointer; flex: 1;">
        <strong>Step ${idx + 1}:</strong> ${escapeHtml(item)}
      </label>
    `;
    container.appendChild(div);
  });
}

function filterDiffSubView(subView) {
  state.diffSubView = subView;
  document.querySelectorAll(".diff-filter-chip").forEach(b => b.classList.remove("active"));
  const btnMap = {
    all: "diffSubTabAll",
    sims: "diffSubTabSims",
    critical: "diffSubTabCritical",
    playbook: "diffSubTabPlaybook"
  };
  const activeBtn = document.getElementById(btnMap[subView]);
  if (activeBtn) activeBtn.classList.add("active");

  const simsContainer = document.getElementById("diffSimsContainer");
  const clausesContainer = document.getElementById("diffClausesContainer");
  const playbookContainer = document.getElementById("diffPlaybookContainer");

  if (subView === 'all') {
    if (simsContainer) simsContainer.style.display = "block";
    if (clausesContainer) clausesContainer.style.display = "block";
    if (playbookContainer) playbookContainer.style.display = "none";
    filterDiffItemsBySeverity('all');
  } else if (subView === 'sims') {
    if (simsContainer) simsContainer.style.display = "block";
    if (clausesContainer) clausesContainer.style.display = "none";
    if (playbookContainer) playbookContainer.style.display = "none";
  } else if (subView === 'critical') {
    if (simsContainer) simsContainer.style.display = "none";
    if (clausesContainer) clausesContainer.style.display = "block";
    if (playbookContainer) playbookContainer.style.display = "none";
    filterDiffItemsBySeverity('critical');
  } else if (subView === 'playbook') {
    if (simsContainer) simsContainer.style.display = "none";
    if (clausesContainer) clausesContainer.style.display = "none";
    if (playbookContainer) playbookContainer.style.display = "block";
  }
}

function filterDiffItemsBySeverity(severity) {
  const cards = document.querySelectorAll("#diffItemsList .diff-item-card");
  cards.forEach(c => {
    if (severity === 'all') {
      c.style.display = "block";
    } else {
      const cardSev = c.getAttribute("data-diff-severity");
      c.style.display = cardSev === severity ? "block" : "none";
    }
  });
}

function setRedlineDisplayMode(mode) {
  state.redlineDisplayMode = mode;
  document.getElementById("redlineInlineBtn").classList.toggle("active", mode === 'inline');
  document.getElementById("redlineSideBtn").classList.toggle("active", mode === 'side');
  if (state.currentDiffData) {
    renderClauseDiffs(state.currentDiffData.differences || [], state.currentDiffData.key_differences || [], state.docAName || "Document A", state.docBName || "Document B");
    if (state.diffSubView === 'critical') {
      filterDiffItemsBySeverity('critical');
    }
  }
}

function bridgeDiffToNegotiationEmail() {
  if (!state.currentDiffData) return;
  switchFeatureTab('playbook');
  
  // Auto-populate clauses selector with the diff categories
  const emailSelector = document.getElementById("emailClausesSelector");
  if (emailSelector) {
    emailSelector.innerHTML = "";
    const items = state.currentDiffData.differences || state.currentDiffData.key_differences || [];
    items.forEach(d => {
      const title = d.clause_title || d.category;
      const div = document.createElement("div");
      div.style.marginBottom = "0.4rem";
      div.innerHTML = `
        <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
          <input type="checkbox" value="${escapeHtml(title)}" checked>
          <span>${escapeHtml(title)}</span>
        </label>
      `;
      emailSelector.appendChild(div);
    });
  }

  const roleSelect = document.getElementById("emailRecipientRole");
  if (roleSelect) {
    roleSelect.value = "Vendor / Counterparty Counsel";
  }

  showToast("Transferred differences into Counter-Proposal Email Drafter!", "success");
}

function renderDiffResults(data, nameA, nameB) {
  renderDiffDashboard(data, nameA, nameB);
}

// TAB 4: Grounded Q&A Chat
function renderSuggestedQuestions(questions) {
  const container = document.getElementById("suggestedQuestionsList");
  container.innerHTML = "";
  questions.forEach(q => {
    const btn = document.createElement("button");
    btn.className = "suggested-q-btn";
    btn.textContent = q;
    btn.onclick = () => askScenario(q);
    container.appendChild(btn);
  });
}

function askScenario(questionText) {
  document.getElementById("chatInput").value = questionText;
  sendQuestion();
}

async function sendQuestion() {
  const input = document.getElementById("chatInput");
  const q = input.value.trim();
  if (!q) return;

  const chatHistory = document.getElementById("chatHistory");

  // Append user message
  const userMsg = document.createElement("div");
  userMsg.className = "chat-msg user";
  userMsg.textContent = q;
  chatHistory.appendChild(userMsg);
  input.value = "";
  chatHistory.scrollTop = chatHistory.scrollHeight;

  // Placeholder bot message
  const botMsg = document.createElement("div");
  botMsg.className = "chat-msg assistant";
  botMsg.innerHTML = `<em>Reviewing contract clauses and generating grounded answer...</em>`;
  chatHistory.appendChild(botMsg);
  chatHistory.scrollTop = chatHistory.scrollHeight;

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        document_text: state.currentDocText,
        question: q,
        api_key: state.apiKey || undefined
      })
    });

    if (!res.ok) throw new Error("Q&A request failed");
    const data = await res.json();

    let citationsHtml = "";
    if (data.citations && data.citations.length > 0) {
      data.citations.forEach(c => {
        citationsHtml += `
          <div class="citation-box">
            <strong>📌 Citation: ${escapeHtml(c.clause_title)}</strong><br>
            <em>"${escapeHtml(c.quote)}"</em>
          </div>
        `;
      });
    }

    botMsg.innerHTML = `
      <div>${escapeHtml(data.answer).replace(/\n/g, '<br>')}</div>
      ${citationsHtml}
      <div style="margin-top: 0.65rem; font-size: 0.88rem; color: #1e40af; background: #eff6ff; padding: 0.5rem 0.75rem; border-radius: 6px;">
        💡 <strong>Practical Takeaway:</strong> ${escapeHtml(data.practical_takeaway)}
      </div>
    `;
    chatHistory.scrollTop = chatHistory.scrollHeight;

  } catch (err) {
    botMsg.innerHTML = `<span style="color: var(--risk-critical);">Error getting answer: ${err.message}</span>`;
  }
}

// TAB 5: Playbook & Negotiation Email Generator
function renderPlaybook(deadlines, checklist, clauses) {
  // Deadlines
  const deadlinesList = document.getElementById("deadlinesList");
  deadlinesList.innerHTML = "";
  deadlines.forEach(d => {
    const item = document.createElement("div");
    item.style.padding = "0.75rem 0";
    item.style.borderBottom = "1px solid #f1f5f9";
    item.innerHTML = `
      <div style="font-weight: 800; font-size: 0.95rem; color: var(--primary);">${escapeHtml(d.timeframe)}</div>
      <div style="font-size: 0.88rem; color: var(--text-secondary);">${escapeHtml(d.action)} (${escapeHtml(d.clause)})</div>
    `;
    deadlinesList.appendChild(item);
  });

  // Checklist
  const checklistContainer = document.getElementById("checklistContainer");
  checklistContainer.innerHTML = "";
  checklist.forEach((item, idx) => {
    const div = document.createElement("div");
    div.className = "checklist-item";
    div.innerHTML = `
      <input type="checkbox" id="chk-${idx}" onchange="toggleCheck(this)">
      <label for="chk-${idx}" style="cursor: pointer;">${escapeHtml(item.task)} <span class="detail-label" style="margin-left: 0.4rem;">[${item.category}]</span></label>
    `;
    checklistContainer.appendChild(div);
  });

  // Clauses selector for email generator
  const emailSelector = document.getElementById("emailClausesSelector");
  emailSelector.innerHTML = "";
  const criticalAndWarning = clauses.filter(c => c.risk_level === 'critical' || c.risk_level === 'warning');
  const targetClauses = criticalAndWarning.length > 0 ? criticalAndWarning : clauses.slice(0, 3);

  targetClauses.forEach((c) => {
    const div = document.createElement("div");
    div.style.marginBottom = "0.4rem";
    div.innerHTML = `
      <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
        <input type="checkbox" value="${escapeHtml(c.section_title)}" checked>
        <span>${escapeHtml(c.section_title)}</span>
      </label>
    `;
    emailSelector.appendChild(div);
  });
}

function toggleCheck(checkbox) {
  const label = checkbox.nextElementSibling;
  if (checkbox.checked) {
    label.style.textDecoration = "line-through";
    label.style.color = "var(--text-muted)";
  } else {
    label.style.textDecoration = "none";
    label.style.color = "var(--text-primary)";
  }
}

async function generateCounterEmail() {
  const role = document.getElementById("emailRecipientRole").value;
  const tone = document.getElementById("emailTone").value;
  const checkboxes = document.querySelectorAll("#emailClausesSelector input[type='checkbox']:checked");
  const selectedClauses = Array.from(checkboxes).map(cb => cb.value);

  if (selectedClauses.length === 0) {
    alert("Please select at least one clause to negotiate in the email.");
    return;
  }

  try {
    const res = await fetch("/api/generate-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipient_role: role,
        clauses_to_negotiate: selectedClauses,
        tone: tone,
        api_key: state.apiKey || undefined
      })
    });

    if (!res.ok) throw new Error("Email generation failed");
    const data = await res.json();

    document.getElementById("emailOutputBox").style.display = "block";
    document.getElementById("emailDraftSubject").value = data.subject;
    document.getElementById("emailDraftBody").value = data.email_body;
    showToast("Counter-proposal email drafted!", "success");

  } catch (err) {
    alert("Error: " + err.message);
  }
}

function copyEmailDraft() {
  const subject = document.getElementById("emailDraftSubject").value;
  const body = document.getElementById("emailDraftBody").value;
  copyToClipboard(`Subject: ${subject}\n\n${body}`, "Email draft copied to clipboard!");
}

// TAB 6: Attorney Consultation Dossier
async function generateAttorneyDossier(analysisData) {
  try {
    const res = await fetch("/api/attorney-brief", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(analysisData)
    });
    if (!res.ok) throw new Error("Brief generation failed");
    const data = await res.json();
    document.getElementById("dossierContent").textContent = data.brief_markdown;
  } catch (err) {
    document.getElementById("dossierContent").textContent = "Could not generate attorney brief: " + err.message;
  }
}

function copyDossierMarkdown() {
  const content = document.getElementById("dossierContent").textContent;
  copyToClipboard(content, "Attorney consultation brief copied as Markdown!");
}

// Feature Tab Switcher
function switchFeatureTab(tabName) {
  document.querySelectorAll(".feature-tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".feature-pane").forEach(p => p.classList.remove("active"));

  const targetPane = document.getElementById(`pane-${tabName}`);
  if (targetPane) targetPane.classList.add("active");

  const activeBtn = Array.from(document.querySelectorAll(".feature-tab-btn")).find(b => b.onclick && b.onclick.toString().includes(tabName));
  if (activeBtn) activeBtn.classList.add("active");
}

// Settings Modal
const settingsModal = document.getElementById("settingsModal");
document.getElementById("btnOpenSettings").onclick = () => settingsModal.classList.add("active");
function closeSettings() { settingsModal.classList.remove("active"); }

function saveApiKey() {
  const key = document.getElementById("geminiApiKeyInput").value.trim();
  state.apiKey = key;
  if (key) {
    localStorage.setItem("jurisclear_gemini_api_key", key);
    updateEngineBadge("⚡ Gemini Active");
    showToast("Gemini API Key saved and activated!", "success");
  } else {
    localStorage.removeItem("jurisclear_gemini_api_key");
    updateEngineBadge("🛡️ Built-in Engine Ready");
    showToast("Using Built-in Legal Intelligence Engine", "info");
  }
  closeSettings();
}

function clearApiKey() {
  localStorage.removeItem("jurisclear_gemini_api_key");
  state.apiKey = "";
  document.getElementById("geminiApiKeyInput").value = "";
  updateEngineBadge("🛡️ Built-in Engine Ready");
  closeSettings();
  showToast("API Key removed. Built-in Engine active.", "info");
}

// Utilities
function copyToClipboard(text, successMsg = "Copied to clipboard!") {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(successMsg, "success");
    }).catch(() => fallbackCopy(text, successMsg));
  } else {
    fallbackCopy(text, successMsg);
  }
}

function fallbackCopy(text, successMsg) {
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
  showToast(successMsg, "success");
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeJsString(str) {
  if (!str) return "";
  return str.replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, " ");
}
