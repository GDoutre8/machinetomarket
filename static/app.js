/* app.js — Machine-to-Market: Fix My Listing */

// ── State ─────────────────────────────────────────────────────────────────────

let lastListing = "";
let lastData    = null;

// ── DOM refs ──────────────────────────────────────────────────────────────────

const rawInput      = document.getElementById("raw-input");
const charCount     = document.getElementById("char-count");
const fixBtn        = document.getElementById("fix-btn");
const copyBtn       = document.getElementById("copy-btn");
const fbBtn         = document.getElementById("fb-btn");
const listingOut    = document.getElementById("listing-out");
const stateIdle     = document.getElementById("state-idle");
const stateLoading  = document.getElementById("state-loading");
const stateError    = document.getElementById("state-error");
const errorMsg      = document.getElementById("error-msg");
const specsWrap     = document.getElementById("specs-wrap");
const specsGrid     = document.getElementById("specs-grid");
const confidenceNote = document.getElementById("confidence-note");
const parsedWrap    = document.getElementById("parsed-wrap");
const parsedGrid    = document.getElementById("parsed-grid");

// ── Char counter ──────────────────────────────────────────────────────────────

rawInput.addEventListener("input", () => {
  const n = rawInput.value.length;
  charCount.textContent = n === 1 ? "1 char" : `${n.toLocaleString()} chars`;
});

// ── Keyboard shortcut: Cmd/Ctrl + Enter ──────────────────────────────────────

rawInput.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    fixListing();
  }
});

// ── Try Example ──────────────────────────────────────────────────────────────

function tryExample() {
  const lines = [
    "2017 Bobcat T590",
    "2400 hours",
    "heat ac cab",
    "74 inch bucket",
    "2 speed",
    "good machine runs great",
    "$32k obo"
  ];
  const example = lines.join("\n");
  rawInput.value = example;
  rawInput.dispatchEvent(new Event("input"));
  fixListing();
}

// ── Main action ───────────────────────────────────────────────────────────────

async function fixListing() {
  const raw = rawInput.value.trim();
  if (!raw) {
    showError("Paste a listing first.");
    return;
  }

  setLoading(true);

  try {
    const res = await fetch("/fix-listing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_text: raw }),
    });

    if (!res.ok) {
      throw new Error(`Server error: ${res.status}`);
    }

    const data = await res.json();

    if (data.error) {
      showError(data.error);
      return;
    }

    renderOutput(data);

  } catch (err) {
    showError(err.message || "Unexpected error. Try again.");
  } finally {
    setLoading(false);
  }
}

// ── Render ────────────────────────────────────────────────────────────────────

function renderOutput(data) {
  lastData    = data;
  // Main listing text — render with credibility line styled
  lastListing = data.cleaned_listing || "";

  // Replace plain <pre> text with HTML so we can style key lines
  const escaped = lastListing
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // First non-empty line = machine headline
  const lines = escaped.split("\n");
  let styled = "";
  let headlineDone = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!headlineDone && line.trim().length > 0) {
      styled += `<span class="listing-headline">${line}</span>\n`;
      headlineDone = true;
    } else if (line.startsWith("✓")) {
      styled += `<span class="oem-source-line">${line}</span>\n`;
    } else {
      styled += line + "\n";
    }
  }
  listingOut.innerHTML = styled;

  setVisible(stateIdle,    false);
  setVisible(stateLoading, false);
  setVisible(stateError,   false);
  setVisible(listingOut,   true);
  setVisible(copyBtn,      true);
  setVisible(fbBtn,        true);

  // Specs panel
  if (data.added_specs && Object.keys(data.added_specs).length > 0) {
    renderSpecs(data.added_specs, data.confidence_note);
    setVisible(specsWrap, true);
  } else {
    setVisible(specsWrap, false);
  }

  // Parsed data panel
  if (data.parsed_machine && Object.keys(data.parsed_machine).length > 0) {
    renderParsed(data.parsed_machine);
    setVisible(parsedWrap, true);
  } else {
    setVisible(parsedWrap, false);
  }
}

function renderSpecs(specs, note) {
  specsGrid.innerHTML = "";

  const labels = {
    horsepower:               "Horsepower",
    operating_weight:         "Operating Weight",
    rated_operating_capacity: "Rated Op. Capacity",
    hydraulic_flow:           "Hydraulic Flow",
    bucket_capacity:          "Bucket Capacity",
    engine:                   "Engine",
    max_travel_speed:         "Max Travel Speed",
    ground_pressure:          "Ground Pressure",
  };

  for (const [key, val] of Object.entries(specs)) {
    if (!val) continue;
    const label = labels[key] || key.replace(/_/g, " ");
    const item = document.createElement("div");
    item.className = "spec-item";
    item.innerHTML = `
      <div class="spec-key">${label}</div>
      <div class="spec-val">${val}</div>
    `;
    specsGrid.appendChild(item);
  }

  confidenceNote.textContent = note || "";
}

function renderParsed(parsed) {
  parsedGrid.innerHTML = "";
  for (const [key, val] of Object.entries(parsed)) {
    if (val === null || val === undefined) continue;
    const item = document.createElement("div");
    item.className = "parsed-item";
    item.innerHTML = `
      <div class="parsed-key">${key}</div>
      <div class="parsed-val">${val}</div>
    `;
    parsedGrid.appendChild(item);
  }
}

// ── Facebook Post Generator ───────────────────────────────────────────────────

function buildFacebookPost(data) {
  const p  = data.parsed_machine || {};
  const sp = data.added_specs    || {};

  const year  = p.year  || "";
  const make  = p.make  || "";
  const model = p.model || "";
  const hours = p.hours ? Number(p.hours).toLocaleString() : null;
  const price = p.price || null;
  const cond  = p.condition || null;
  const atts  = p.attachments || null;
  const feats = Array.isArray(p.features) ? p.features : [];

  const lines = [];

  // Headline
  const headParts = [year, make, model].filter(Boolean);
  let headline = headParts.length ? headParts.join(" ") : "Heavy Equipment for Sale";
  if (hours) headline += ` — ${hours} Hours`;
  lines.push(headline);
  lines.push("");

  // Features block
  const featLines = [];
  if (atts) {
    atts.split(", ").forEach(a => featLines.push(a.trim()));
  }
  if (cond) featLines.push(cond);
  feats.forEach(f => {
    // Skip warranty lines (too long for FB feature block)
    if (!f.toLowerCase().includes("warranty")) featLines.push(f);
  });
  if (featLines.length) {
    featLines.forEach(f => lines.push(f.charAt(0).toUpperCase() + f.slice(1)));
    lines.push("");
  }

  // Machine Specs
  const specMap = {
    horsepower:               "Gross horsepower",
    operating_weight:         "Operating weight",
    rated_operating_capacity: "Rated operating capacity",
    hydraulic_flow:           "Auxiliary hydraulic flow",
    engine:                   "Engine",
    max_travel_speed:         "Max travel speed",
    bucket_capacity:          "Bucket capacity / dig depth",
  };
  const specLines = Object.entries(specMap)
    .filter(([k]) => sp[k])
    .map(([k, label]) => `• ${label}: ${sp[k]}`);

  if (specLines.length) {
    lines.push("Machine Specs:");
    specLines.forEach(s => lines.push(s));
    lines.push("");
  }

  // Price
  if (price) {
    lines.push(price.includes("OBO") ? price : price + " OBO");
  }

  // Location / Contact — omit entirely if not detected
  if (p.location) lines.push(p.location);
  if (p.contact)  lines.push(p.contact);
  lines.push("");

  // Hashtags
  const tags = [];
  if (make)  tags.push(`#${make.toLowerCase().replace(/[^a-z0-9]/g, "")}`);
  if (model) tags.push(`#${model.toLowerCase().replace(/[^a-z0-9]/g, "")}`);
  tags.push("#heavyequipment", "#equipmentdealer", "#usedequipment");
  lines.push(tags.join(" "));

  return lines.join("\n");
}

async function copyFacebookPost() {
  if (!lastData) return;
  const post = buildFacebookPost(lastData);
  try {
    await navigator.clipboard.writeText(post);
    fbBtn.textContent = "Facebook Post Copied ✓";
    fbBtn.classList.add("copied");
    setTimeout(() => {
      fbBtn.textContent = "Copy Facebook Post";
      fbBtn.classList.remove("copied");
    }, 2200);
  } catch {
    // Fallback
    const ta = document.createElement("textarea");
    ta.value = post;
    ta.style.position = "fixed";
    ta.style.opacity  = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    fbBtn.textContent = "Facebook Post Copied ✓";
    setTimeout(() => { fbBtn.textContent = "Copy Facebook Post"; }, 2200);
  }
}

// ── Copy ──────────────────────────────────────────────────────────────────────

async function copyListing() {
  if (!lastListing) return;
  try {
    await navigator.clipboard.writeText(lastListing);
    copyBtn.textContent = "Copied ✓";
    copyBtn.classList.add("copied");
    setTimeout(() => {
      copyBtn.textContent = "Copy ↗";
      copyBtn.classList.remove("copied");
    }, 2000);
  } catch {
    // Fallback for browsers that block clipboard
    const ta = document.createElement("textarea");
    ta.value = lastListing;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    copyBtn.textContent = "Copied ✓";
    setTimeout(() => { copyBtn.textContent = "Copy ↗"; }, 2000);
  }
}

// ── UI helpers ────────────────────────────────────────────────────────────────

function setLoading(on) {
  fixBtn.disabled = on;
  fixBtn.querySelector(".btn-text").textContent = on ? "Processing…" : "Fix My Listing";

  if (on) {
    setVisible(stateIdle,    false);
    setVisible(stateError,   false);
    setVisible(listingOut,   false);
    setVisible(stateLoading, true);
    setVisible(copyBtn,      false);
    setVisible(fbBtn,        false);
    setVisible(specsWrap,    false);
    setVisible(parsedWrap,   false);
  }
}

function showError(msg) {
  errorMsg.textContent = msg;
  setVisible(stateIdle,    false);
  setVisible(stateLoading, false);
  setVisible(listingOut,   false);
  setVisible(stateError,   true);
  setVisible(copyBtn,      false);
  setVisible(fbBtn,        false);
}

function setVisible(el, visible) {
  el.style.display = visible ? "" : "none";
}
