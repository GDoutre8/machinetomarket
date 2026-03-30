/* app.js — Machine-to-Market: Fix My Listing */

// ── State ─────────────────────────────────────────────────────────────────────

let lastListing  = "";
let lastData     = null;
let isProcessing = false;

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
const outputsWrap   = document.getElementById("outputs-wrap");
const outputsGrid   = document.getElementById("outputs-grid");
const outputsLevel  = document.getElementById("outputs-level");

// ── Toggle controls ────────────────────────────────────────────────────────────

const toggleSpecSheet  = document.getElementById("toggle-spec-sheet");
const toggleVariants   = document.getElementById("toggle-variants");
const togglePackage    = document.getElementById("toggle-package");
const toggleWalkaround = document.getElementById("toggle-walkaround");
const wrapVariants     = document.getElementById("wrap-variants");
const wrapWalkaround   = document.getElementById("wrap-walkaround");

// ── Pack / photo upload refs ──────────────────────────────────────────────────

const photoInput      = document.getElementById("photo-input");
const photoDrop       = document.getElementById("photo-drop");
const photoDropLabel  = document.getElementById("photo-drop-label");
const photoBadge      = document.getElementById("photo-badge");
const packReadyWrap   = document.getElementById("pack-ready-wrap");
const packCardMachine = document.getElementById("pack-card-machine");
const packCardStats   = document.getElementById("pack-card-stats");
const packStatusBadge = document.getElementById("pack-status-badge");
const packManifest    = document.getElementById("pack-manifest");
const packWarningsBox = document.getElementById("pack-warnings-box");
const packWarningsList = document.getElementById("pack-warnings-list");
const packDownloadBtn = document.getElementById("pack-download-btn");

let selectedPhotos = [];   // FileList-like array

// ── Photo upload wiring ───────────────────────────────────────────────────────

photoInput.addEventListener("change", () => {
  selectedPhotos = Array.from(photoInput.files || []);
  updatePhotoDrop();
});

photoDrop.addEventListener("dragover", (e) => {
  e.preventDefault();
  photoDrop.classList.add("drag-over");
});
photoDrop.addEventListener("dragleave", () => photoDrop.classList.remove("drag-over"));
photoDrop.addEventListener("drop", (e) => {
  e.preventDefault();
  photoDrop.classList.remove("drag-over");
  const files = Array.from(e.dataTransfer.files || []).filter(f =>
    /\.(jpe?g|png|webp|heic|heif|bmp|tiff?)$/i.test(f.name)
  );
  if (files.length) {
    selectedPhotos = files;
    updatePhotoDrop();
  }
});

function updatePhotoDrop() {
  const n = selectedPhotos.length;
  if (n === 0) {
    photoDropLabel.textContent = "Drop photos here or click to upload";
    photoDrop.classList.remove("has-files");
    photoBadge.style.display = "none";
    // Walkaround needs photos — disable when none selected
    toggleWalkaround.disabled = true;
    wrapWalkaround.classList.add("disabled");
  } else {
    photoDropLabel.textContent = `${n} photo${n > 1 ? "s" : ""} selected — click to change`;
    photoDrop.classList.add("has-files");
    photoBadge.textContent = n;
    photoBadge.style.display = "inline-block";
    toggleWalkaround.disabled = false;
    wrapWalkaround.classList.remove("disabled");
  }
}

// Disable walkaround on load (no photos yet)
toggleWalkaround.disabled = true;
wrapWalkaround.classList.add("disabled");

// ── Reset all result panels (call before every new run) ───────────────────────

function resetAllPanels() {
  setVisible(packReadyWrap, false);
  setVisible(specsWrap,     false);
  setVisible(outputsWrap,   false);
  setVisible(parsedWrap,    false);
  setVisible(listingOut,    false);
  setVisible(copyBtn,       false);
  setVisible(fbBtn,         false);
  setVisible(stateError,    false);
  packManifest.innerHTML    = "";
  packWarningsList.innerHTML = "";
  packWarningsBox.style.display = "none";
}

// ── Dealer info toggle ────────────────────────────────────────────────────────

function toggleDealer() {
  const fields = document.getElementById("dealer-fields");
  const arrow  = document.getElementById("dealer-arrow");
  const open   = fields.style.display === "none";
  fields.style.display = open ? "" : "none";
  arrow.innerHTML = open ? "&#9650;" : "&#9660;";
}

// When Spec Sheet is unchecked, disable Variants (variants require a spec sheet)
toggleSpecSheet.addEventListener("change", () => {
  if (!toggleSpecSheet.checked) {
    toggleVariants.checked  = false;
    toggleVariants.disabled = true;
    wrapVariants.classList.add("disabled");
  } else {
    toggleVariants.disabled = false;
    wrapVariants.classList.remove("disabled");
  }
});

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
  rawInput.scrollTop = 0;
  rawInput.dispatchEvent(new Event("input"));
  fixListing();
}

// ── Main action ───────────────────────────────────────────────────────────────

async function fixListing() {
  if (isProcessing) return;
  const raw = rawInput.value.trim();
  if (!raw) {
    showError("Paste a listing first.");
    return;
  }

  isProcessing = true;
  resetAllPanels();

  const genPackage  = togglePackage.checked;
  const isPackBuild = selectedPhotos.length > 0 && genPackage;
  const loadLabel   = isPackBuild
    ? (toggleWalkaround.checked ? "Generating pack + video..." : "Generating pack...")
    : "Processing...";
  setLoading(true, loadLabel);

  // When photos are uploaded + ZIP Package is checked → use pack endpoint
  if (isPackBuild) {
    await buildListingPack(raw);
    isProcessing = false;
    return;
  }

  try {
    const specLevel   = document.querySelector('input[name="spec_level"]:checked')?.value || "quick";
    const genSheet    = toggleSpecSheet.checked;
    const genVariants = toggleVariants.checked;

    const res = await fetch("/fix-listing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        raw_text:                     raw,
        spec_level:                   specLevel,
        generate_spec_sheet:          genSheet,
        generate_spec_sheet_variants: genVariants,
        generate_listing_package:     genPackage,
      }),
    });

    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const data = await res.json();
    if (data.error) { showError(data.error); return; }
    renderOutput(data);

  } catch (err) {
    showError(err.message || "Unexpected error. Try again.");
  } finally {
    isProcessing = false;
    setLoading(false);
  }
}

// ── Listing Pack endpoint (multipart, photos present) ─────────────────────────

async function buildListingPack(raw) {
  try {
    const specLevel = document.querySelector('input[name="spec_level"]:checked')?.value || "full";

    const fd = new FormData();
    fd.append("raw_text",   raw);
    fd.append("spec_level", specLevel);
    fd.append("generate_spec_sheet_flag",   toggleSpecSheet.checked  ? "true" : "false");
    fd.append("generate_image_pack_flag",   "true");
    fd.append("generate_walkaround_flag",   toggleWalkaround.checked ? "true" : "false");

    const dealerName     = document.getElementById("dealer-name")?.value.trim()     || "";
    const dealerPhone    = document.getElementById("dealer-phone")?.value.trim()    || "";
    const dealerEmail    = document.getElementById("dealer-email")?.value.trim()    || "";
    const dealerLocation = document.getElementById("dealer-location")?.value.trim() || "";
    if (dealerName)     fd.append("dealer_name", dealerName);
    if (dealerPhone)    fd.append("phone",        dealerPhone);
    if (dealerEmail)    fd.append("email",        dealerEmail);
    if (dealerLocation) fd.append("location",     dealerLocation);

    for (const file of selectedPhotos) {
      fd.append("photos", file);
    }

    const res = await fetch("/generate-listing-pack", { method: "POST", body: fd });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const data = await res.json();

    if (data.error) { showError(data.error); return; }

    renderPackReady(data);

  } catch (err) {
    showError(err.message || "Pack generation failed. Try again.");
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

  // Specs panel — render from pre-formatted display_specs (backend is source of truth)
  if (data.display_specs && data.display_specs.length > 0) {
    renderSpecs(data.display_specs, data.confidence_note);
    setVisible(specsWrap, true);
  } else {
    setVisible(specsWrap, false);
  }

  // Output files panel
  renderOutputAssets(data);

  // Parsed data panel
  if (data.parsed_machine && Object.keys(data.parsed_machine).length > 0) {
    renderParsed(data.parsed_machine);
    setVisible(parsedWrap, true);
  } else {
    setVisible(parsedWrap, false);
  }
}

// ── Output assets panel ───────────────────────────────────────────────────────

const SPEC_LEVEL_LABELS = { quick: "Quick Specs", dealer: "Dealer Specs", full: "Full Specs" };

const VARIANT_LABELS = {
  "4x5":       "Feed 4×5  (1200×1500)",
  "square":    "Square  (1200×1200)",
  "story":     "Story  (1080×1920)",
  "landscape": "Landscape  (1200×630)",
};

function renderOutputAssets(data) {
  outputsGrid.innerHTML = "";

  const oa = data.output_assets;
  if (!oa || (!oa.spec_sheet && !oa.listing_package)) {
    setVisible(outputsWrap, false);
    return;
  }

  // Badge shows which spec level was used
  outputsLevel.textContent = SPEC_LEVEL_LABELS[data.spec_level] || data.spec_level || "";

  // Base spec sheet
  if (oa.spec_sheet) {
    outputsGrid.appendChild(makeOutputItem("Spec Sheet", oa.spec_sheet.split("/").pop(), oa.spec_sheet));
  }

  // Sized variants — iterate in display order; skip nulls
  for (const key of ["4x5", "square", "story", "landscape"]) {
    const url = oa.variants?.[key];
    if (url) {
      outputsGrid.appendChild(makeOutputItem(VARIANT_LABELS[key] || key, url.split("/").pop(), url));
    }
  }

  // ZIP package — force download
  if (oa.listing_package) {
    outputsGrid.appendChild(makeOutputItem("Listing Package (ZIP)", oa.listing_package.split("/").pop(), oa.listing_package, true));
  }

  setVisible(outputsWrap, true);
}

function makeOutputItem(label, fname, href, download = false) {
  const item = document.createElement("div");
  item.className = "output-item";
  item.innerHTML = `
    <div class="output-item-label">${label}</div>
    <a class="output-item-link" href="${href}" ${download ? "download" : 'target="_blank"'}>${fname}</a>
  `;
  return item;
}

// items = [{key, label, value}, ...] — pre-formatted by backend, no mapping needed here
function renderSpecs(items, note) {
  specsGrid.innerHTML = "";
  for (const { label, value } of items) {
    const item = document.createElement("div");
    item.className = "spec-item";
    item.innerHTML = `
      <div class="spec-key">${label}</div>
      <div class="spec-val">${value}</div>
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
  const p            = data.parsed_machine || {};
  const displaySpecs = data.display_specs  || [];

  const year  = p.year  || "";
  const make  = p.make  || "";
  const model = p.model || "";
  const hours = p.machine_hours ? Number(p.machine_hours).toLocaleString() : null;
  const price = p.price || null;
  const cond  = p.condition || null;
  const atts  = p.attachments || null;
  // parsed_machine.features is a comma-joined string from the service
  const feats = p.features
    ? (Array.isArray(p.features) ? p.features : p.features.split(", ").filter(Boolean))
    : [];

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

  // Machine Specs — use backend-formatted display_specs items directly
  const specLines = displaySpecs.map(({ label, value }) => `• ${label}: ${value}`);

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

// ── Pack ready renderer ───────────────────────────────────────────────────────

function renderPackReady(data) {
  const outs = data.outputs || {};
  const wk   = data.walkaround || {};

  // Machine name + stats
  packCardMachine.textContent = data.machine_match || "Machine";
  const statParts = [];
  if (data.spec_count)  statParts.push(`${data.spec_count} specs`);
  if (data.image_count) statParts.push(`${data.image_count} photos`);
  packCardStats.textContent = statParts.join(" · ");

  // Status badge
  const hasWarnings = data.warnings && data.warnings.length > 0;
  packStatusBadge.textContent = hasWarnings ? "Pack Ready \u2014 with warnings" : "Pack Ready";
  packStatusBadge.className   = "pack-status-badge" + (hasWarnings ? " pack-status-badge-warn" : "");

  // Manifest rows
  packManifest.innerHTML = "";
  const manifestItems = [
    { label: "Listing Text",     ok: !!outs.listing_txt,    url: outs.listing_txt,    requested: true },
    { label: "Spec Sheet PNG",   ok: !!outs.spec_sheet_png, url: outs.spec_sheet_png, requested: data.spec_count > 0 },
    { label: "Image Pack",       ok: !!outs.image_pack_folder, url: null,             requested: data.image_count > 0 },
    { label: "Walkaround Video", ok: wk.included,           url: outs.walkaround_mp4, requested: wk.requested, status: wk.status },
  ];
  for (const item of manifestItems) {
    let icon, iconClass, statusText;
    if (item.ok) {
      icon = "\u2713"; iconClass = "mi-ok";   statusText = "Included";
    } else if (!item.requested) {
      icon = "\u2014"; iconClass = "mi-skip"; statusText = "Not requested";
    } else {
      icon = "\u2717"; iconClass = "mi-fail";
      statusText = item.status ? item.status.replace(/_/g, " ") : "Failed";
    }
    const row = document.createElement("div");
    row.className = "manifest-row";
    row.innerHTML = `
      <span class="manifest-icon ${iconClass}">${icon}</span>
      <span class="manifest-label">${item.label}</span>
      <span class="manifest-status">${statusText}</span>
      ${item.url ? `<a class="manifest-link" href="${item.url}" target="_blank">View</a>` : ""}
    `;
    packManifest.appendChild(row);
  }

  // Warnings box
  if (hasWarnings) {
    packWarningsBox.style.display = "";
    packWarningsList.innerHTML = "";
    for (const w of data.warnings) {
      const li = document.createElement("li");
      li.textContent = w;
      packWarningsList.appendChild(li);
    }
  } else {
    packWarningsBox.style.display = "none";
  }

  // Download button
  const zipUrl = outs.zip_file;
  if (zipUrl) {
    const zipPath = outs.zip_path;
    packDownloadBtn.href = zipPath
      ? `/download-pack?path=${encodeURIComponent(zipPath)}`
      : zipUrl;
    packDownloadBtn.removeAttribute("disabled");
    packDownloadBtn.textContent = "\u2193 Download ZIP Pack";
  } else {
    packDownloadBtn.setAttribute("disabled", "");
    packDownloadBtn.textContent = "ZIP not available";
  }

  setVisible(packReadyWrap, true);
  setVisible(outputsWrap,   false);
}

// ── UI helpers ────────────────────────────────────────────────────────────────

function setLoading(on, label) {
  fixBtn.disabled = on;
  fixBtn.querySelector(".btn-text").textContent = on ? (label || "Processing...") : "Fix My Listing";
  const loadingLabel = document.querySelector(".loading-label");
  if (loadingLabel) loadingLabel.textContent = on ? (label || "Processing...") : "Processing...";

  if (on) {
    setVisible(stateIdle,     false);
    setVisible(stateError,    false);
    setVisible(listingOut,    false);
    setVisible(stateLoading,  true);
    setVisible(copyBtn,       false);
    setVisible(fbBtn,         false);
    setVisible(specsWrap,     false);
    setVisible(parsedWrap,    false);
    setVisible(outputsWrap,   false);
    setVisible(packReadyWrap, false);
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
