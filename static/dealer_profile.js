/* dealer_profile.js — dealer badge profile UI + localStorage persistence + preset library */
(function () {
  'use strict';

  var STORAGE_KEY = 'mtm_dealer_profile';
  var PRESETS_KEY = 'mtm_dealer_profile_presets';

  // Module-level logo state — shared between initDealerProfile and read/write helpers
  var _logoDataUrl = null;

  // ── Storage ────────────────────────────────────────────────────────────────

  function getDealerProfile() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) { return null; }
  }

  function saveDealerProfileData(profile) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(profile)); } catch (_) {}
  }

  // ── Preset library ─────────────────────────────────────────────────────────

  function loadProfilePresets() {
    try {
      var raw = localStorage.getItem(PRESETS_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (_) { return []; }
  }

  function saveProfilePreset(name, profile) {
    var presets = loadProfilePresets();
    presets.push({
      id:           Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      name:         String(name || 'Preset').slice(0, 40),
      createdAt:    new Date().toISOString(),
      companyName:  profile.companyName  || '',
      contactName:  profile.contactName  || '',
      phone:        profile.phone        || '',
      role:         profile.role         || '',
      logoDataUrl:  profile.logoDataUrl  || null,
      accentColor:  profile.accentColor  || 'yellow',
    });
    try { localStorage.setItem(PRESETS_KEY, JSON.stringify(presets)); } catch (_) {}
    return presets;
  }

  function deleteProfilePreset(id) {
    var presets = loadProfilePresets().filter(function (p) { return p.id !== id; });
    try { localStorage.setItem(PRESETS_KEY, JSON.stringify(presets)); } catch (_) {}
    return presets;
  }

  // ── Phone auto-format: (###) ###-#### ─────────────────────────────────────

  function formatPhone(raw) {
    var digits = raw.replace(/\D/g, '').slice(0, 10);
    if (digits.length >= 7) return '(' + digits.slice(0, 3) + ') ' + digits.slice(3, 6) + '-' + digits.slice(6);
    if (digits.length >= 4) return '(' + digits.slice(0, 3) + ') ' + digits.slice(3);
    if (digits.length >= 1) return '(' + digits;
    return '';
  }

  // ── Form state read/write ──────────────────────────────────────────────────
  // These operate on the dp-* inputs rendered by initDealerProfile.
  // _formEl is accepted for API symmetry but the IDs are document-global.

  function readProfileFromFormState(_formEl) {
    var companyEl = document.getElementById('dp-company');
    if (!companyEl) return null;
    var company = (companyEl.value || '').trim();
    var contact = ((document.getElementById('dp-contact') || {}).value || '').trim();
    var phone   = ((document.getElementById('dp-phone')   || {}).value || '').trim();
    var role    = ((document.getElementById('dp-role')    || {}).value || '').trim();
    // Return null only when every field is blank — any single filled field
    // is enough to render a badge. With the overlay gone this is the only
    // branding path; silently skipping it when company is blank but contact
    // or phone is set would produce unbranded photos with no warning.
    var accentColor = 'yellow';
    var swatchEls = document.querySelectorAll('[data-accent-swatch]');
    swatchEls.forEach(function (el) {
      if (el.getAttribute('aria-pressed') === 'true') accentColor = el.getAttribute('data-accent-swatch');
    });
    if (!company && !contact && !phone && !_logoDataUrl) return null;
    return {
      companyName:  company,
      contactName:  contact,
      phone:        phone,
      role:         role,
      logoDataUrl:  _logoDataUrl || null,
      accentColor:  accentColor,
    };
  }

  function writeProfileToFormState(_formEl, profile) {
    if (!profile) return;
    var companyEl = document.getElementById('dp-company');
    var contactEl = document.getElementById('dp-contact');
    var phoneEl   = document.getElementById('dp-phone');
    var roleEl    = document.getElementById('dp-role');
    var logoDrop  = document.getElementById('dp-logo-drop');
    var logoLabel = document.getElementById('dp-logo-label');
    var statusEl  = document.getElementById('dp-status');

    if (companyEl) companyEl.value = profile.companyName  || '';
    if (contactEl) contactEl.value = profile.contactName  || '';
    if (roleEl)    roleEl.value    = profile.role         || '';
    if (phoneEl)   phoneEl.value   = profile.phone        || '';

    _logoDataUrl = profile.logoDataUrl || null;
    var savedAccent = profile.accentColor || 'yellow';
    document.querySelectorAll('[data-accent-swatch]').forEach(function (el) {
      var active = el.getAttribute('data-accent-swatch') === savedAccent;
      el.setAttribute('aria-pressed', active ? 'true' : 'false');
      el.style.outline = active ? '2px solid #fff' : '2px solid transparent';
      el.style.outlineOffset = '2px';
    });
    if (logoDrop) {
      if (_logoDataUrl) {
        logoDrop.classList.add('has-files');
        if (logoLabel) logoLabel.innerHTML = '<strong>Logo loaded</strong> \u2014 click to replace';
      } else {
        logoDrop.classList.remove('has-files');
        if (logoLabel) logoLabel.innerHTML = '<strong>Click to upload logo</strong>';
      }
    }

    if (statusEl) {
      var hasProfile = !!(profile.companyName || '').trim();
      statusEl.textContent = hasProfile ? '\u2014 Badge Active' : '\u2014 No Profile (badge off)';
      statusEl.style.color = hasProfile ? '#5cc58a' : 'var(--dim)';
    }

    saveDealerProfileData(profile);
  }

  // ── hydrateProfile ─────────────────────────────────────────────────────────

  function hydrateProfile(_containerId) {
    var profile = getDealerProfile();
    if (profile) writeProfileToFormState(null, profile);
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  function fileToBase64(file) {
    return new Promise(function (res, rej) {
      var reader     = new FileReader();
      reader.onload  = function (e) { res(e.target.result); };
      reader.onerror = rej;
      reader.readAsDataURL(file);
    });
  }

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Preset list renderer (called by initDealerProfile) ────────────────────

  function renderPresetList(listEl) {
    var presets = loadProfilePresets();
    if (presets.length === 0) {
      listEl.innerHTML = '<div style="font-size:11px;color:var(--dim);padding:4px 0;">No presets saved.</div>';
      return;
    }
    var html = '';
    presets.forEach(function (p) {
      html +=
        '<div style="display:flex;align-items:center;gap:6px;padding:6px 10px;margin-bottom:6px;' +
        'border:1px solid rgba(255,255,255,.1);border-radius:3px;background:rgba(255,255,255,.03);">' +
        '<span style="flex:1;font-size:13px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' +
        escHtml(p.name) + '</span>' +
        '<button type="button" data-preset-load="' + escHtml(p.id) + '" ' +
        'style="font-family:var(--mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase;' +
        'background:rgba(92,197,138,.1);border:1px solid rgba(92,197,138,.3);color:#5cc58a;' +
        'padding:4px 8px;border-radius:3px;cursor:pointer;flex-shrink:0;">Load</button>' +
        '<button type="button" data-preset-delete="' + escHtml(p.id) + '" ' +
        'style="background:rgba(255,100,100,.1);border:1px solid rgba(255,100,100,.25);color:#ff8d8d;' +
        'padding:4px 7px;border-radius:3px;cursor:pointer;font-size:12px;flex-shrink:0;">\u2715</button>' +
        '</div>';
    });
    listEl.innerHTML = html;

    listEl.querySelectorAll('[data-preset-load]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id     = btn.getAttribute('data-preset-load');
        var preset = loadProfilePresets().filter(function (p) { return p.id === id; })[0];
        if (!preset) return;
        writeProfileToFormState(null, preset);
        // Expand fields panel if collapsed
        var fields = document.getElementById('dp-fields');
        var arrow  = document.getElementById('dp-arrow');
        if (fields && fields.style.display === 'none') {
          fields.style.display = '';
          if (arrow) arrow.innerHTML = '&#9650;';
        }
      });
    });

    listEl.querySelectorAll('[data-preset-delete]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = btn.getAttribute('data-preset-delete');
        deleteProfilePreset(id);
        renderPresetList(listEl);
      });
    });
  }

  // ── UI init ────────────────────────────────────────────────────────────────

  function initDealerProfile(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = [
      '<div id="dp-header" style="display:flex;align-items:center;gap:0;cursor:pointer;user-select:none;">',
        '<div class="section-label" style="margin-bottom:0;cursor:pointer;">',
          'Dealer Badge Profile',
        '</div>',
        '<span id="dp-status" style="font-family:var(--body);font-size:11px;font-weight:400;',
              'text-transform:none;letter-spacing:0;margin-left:10px;color:var(--dim);flex-shrink:0;">',
          'loading\u2026',
        '</span>',
        '<span id="dp-arrow" style="margin-left:auto;font-size:12px;color:var(--dim);">&#9660;</span>',
      '</div>',
      '<p style="font-size:12px;color:var(--muted);margin:6px 0 0;">',
        'Set once \u2014 automatically stamped on every downloaded photo pack.',
      '</p>',
      '<div id="dp-fields" style="display:none;margin-top:14px;">',
        '<div class="field-row" style="margin-bottom:14px;">',
          '<div class="field">',
            '<label for="dp-company">Company Name <span class="req">*</span></label>',
            '<input type="text" id="dp-company" placeholder="Acme Equipment" maxlength="50" autocomplete="organization">',
          '</div>',
          '<div class="field">',
            '<label for="dp-role">Role',
            ' <span style="font-weight:400;color:var(--dim);font-size:11px;">Optional</span></label>',
            '<input type="text" id="dp-role" placeholder="Sales \u00b7 Owner \u00b7 Dealer" maxlength="30">',
          '</div>',
        '</div>',
        '<div class="field-row" style="margin-bottom:14px;">',
          '<div class="field">',
            '<label for="dp-contact">Contact Name',
            ' <span style="font-weight:400;color:var(--dim);font-size:11px;">Optional</span></label>',
            '<input type="text" id="dp-contact" placeholder="Jane Smith" maxlength="40" autocomplete="name">',
          '</div>',
          '<div class="field">',
            '<label for="dp-phone">Phone',
            ' <span style="font-weight:400;color:var(--dim);font-size:11px;">Optional</span></label>',
            '<input type="text" id="dp-phone" placeholder="(555) 123-4567" maxlength="16" inputmode="tel" autocomplete="tel">',
          '</div>',
        '</div>',
        '<div class="field-row single" style="margin-bottom:6px;">',
          '<div class="field">',
            '<label for="dp-logo-input">Company Logo',
            ' <span style="font-weight:400;color:var(--dim);font-size:11px;">Optional \u2014 PNG with transparency recommended</span></label>',
            '<div class="photo-drop" id="dp-logo-drop" style="min-height:38px;padding:8px 12px;"',
                 ' onclick="document.getElementById(\'dp-logo-input\').click()">',
              '<div id="dp-logo-label" class="photo-drop-label">',
                '<strong>Click to upload logo</strong>',
              '</div>',
            '</div>',
            '<input type="file" id="dp-logo-input" accept="image/png,image/jpeg,image/webp,image/*" style="display:none">',
          '</div>',
        '</div>',
        '<div class="field-row single" style="margin-bottom:14px;margin-top:14px;">',
          '<div class="field">',
            '<label>Card Theme <span style="font-weight:400;color:var(--dim);font-size:11px;">Hero card accent color</span></label>',
            '<div style="display:flex;gap:8px;align-items:center;margin-top:6px;">',
              '<button type="button" data-accent-swatch="yellow" aria-pressed="true"  title="Yellow" style="width:22px;height:22px;border-radius:50%;background:#FFC20E;border:none;cursor:pointer;outline:2px solid #fff;outline-offset:2px;flex-shrink:0;"></button>',
              '<button type="button" data-accent-swatch="red"    aria-pressed="false" title="Red"    style="width:22px;height:22px;border-radius:50%;background:#C8102E;border:none;cursor:pointer;outline:2px solid transparent;outline-offset:2px;flex-shrink:0;"></button>',
              '<button type="button" data-accent-swatch="blue"   aria-pressed="false" title="Blue"   style="width:22px;height:22px;border-radius:50%;background:#1E4D8C;border:none;cursor:pointer;outline:2px solid transparent;outline-offset:2px;flex-shrink:0;"></button>',
              '<button type="button" data-accent-swatch="green"  aria-pressed="false" title="Green"  style="width:22px;height:22px;border-radius:50%;background:#2C5F3E;border:none;cursor:pointer;outline:2px solid transparent;outline-offset:2px;flex-shrink:0;"></button>',
              '<button type="button" data-accent-swatch="orange" aria-pressed="false" title="Orange" style="width:22px;height:22px;border-radius:50%;background:#D85A15;border:none;cursor:pointer;outline:2px solid transparent;outline-offset:2px;flex-shrink:0;"></button>',
            '</div>',
          '</div>',
        '</div>',
        '<div style="font-size:11px;color:var(--dim);">Changes save automatically.</div>',
        // ── Preset section ──────────────────────────────────────────────────
        '<div id="dp-preset-section" style="margin-top:18px;padding-top:14px;border-top:1px solid rgba(255,255,255,.08);">',
          '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">',
            '<span style="font-family:var(--mono);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--dim);">Presets</span>',
            '<button type="button" id="dp-preset-save-btn"',
                    ' style="font-family:var(--mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase;',
                    'background:rgba(232,169,32,.1);border:1px solid rgba(232,169,32,.28);color:var(--mtm-yellow,#f5c400);',
                    'padding:4px 10px;border-radius:3px;cursor:pointer;">+ Save as Preset</button>',
          '</div>',
          '<div id="dp-preset-list"></div>',
          '<div id="dp-preset-name-row" style="display:none;margin-top:8px;gap:6px;align-items:center;">',
            '<input type="text" id="dp-preset-name" placeholder="Preset name\u2026" maxlength="40"',
                   ' style="flex:1;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.14);',
                   'color:var(--text);border-radius:3px;padding:7px 10px;font-family:var(--body);font-size:13px;min-height:0;">',
            '<button type="button" id="dp-preset-confirm"',
                    ' style="font-family:var(--mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase;',
                    'background:rgba(92,197,138,.14);border:1px solid rgba(92,197,138,.3);color:#5cc58a;',
                    'padding:6px 12px;border-radius:3px;cursor:pointer;white-space:nowrap;">Save</button>',
            '<button type="button" id="dp-preset-cancel"',
                    ' style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.12);',
                    'color:var(--dim);padding:6px 10px;border-radius:3px;cursor:pointer;font-size:12px;">\u2715</button>',
          '</div>',
        '</div>',
      '</div>',
    ].join('');

    var header           = document.getElementById('dp-header');
    var fields           = document.getElementById('dp-fields');
    var arrow            = document.getElementById('dp-arrow');
    var statusEl         = document.getElementById('dp-status');
    var companyEl        = document.getElementById('dp-company');
    var roleEl           = document.getElementById('dp-role');
    var contactEl        = document.getElementById('dp-contact');
    var phoneEl          = document.getElementById('dp-phone');
    var logoInput        = document.getElementById('dp-logo-input');
    var logoLabel        = document.getElementById('dp-logo-label');
    var logoDrop         = document.getElementById('dp-logo-drop');
    var presetList       = document.getElementById('dp-preset-list');
    var presetSaveBtn    = document.getElementById('dp-preset-save-btn');
    var presetNameRow    = document.getElementById('dp-preset-name-row');
    var presetNameInput  = document.getElementById('dp-preset-name');
    var presetConfirm    = document.getElementById('dp-preset-confirm');
    var presetCancel     = document.getElementById('dp-preset-cancel');

    // ── Status indicator ───────────────────────────────────────────────────

    function updateStatus() {
      var hasProfile = !!(companyEl.value || '').trim();
      statusEl.textContent = hasProfile ? '\u2014 Badge Active' : '\u2014 No Profile (badge off)';
      statusEl.style.color = hasProfile ? '#5cc58a' : 'var(--dim)';
    }

    // ── Save to localStorage ───────────────────────────────────────────────

    function getSelectedAccent() {
      var accent = 'yellow';
      document.querySelectorAll('[data-accent-swatch]').forEach(function (el) {
        if (el.getAttribute('aria-pressed') === 'true') accent = el.getAttribute('data-accent-swatch');
      });
      return accent;
    }

    function save() {
      var company = (companyEl.value || '').trim();
      if (!company) {
        try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
        updateStatus();
        return;
      }
      saveDealerProfileData({
        companyName:  company,
        contactName:  (contactEl.value || '').trim(),
        phone:        (phoneEl.value   || '').trim(),
        role:         (roleEl.value    || '').trim(),
        logoDataUrl:  _logoDataUrl,
        accentColor:  getSelectedAccent(),
      });
      updateStatus();
    }

    // ── Restore from localStorage ──────────────────────────────────────────

    function restoreFields() {
      var profile = getDealerProfile();
      if (!profile) { updateStatus(); return; }
      companyEl.value = profile.companyName  || '';
      roleEl.value    = profile.role         || '';
      contactEl.value = profile.contactName  || '';
      phoneEl.value   = formatPhone(profile.phone || '');
      if (profile.logoDataUrl) {
        _logoDataUrl = profile.logoDataUrl;
        logoDrop.classList.add('has-files');
        logoLabel.innerHTML = '<strong>Logo loaded</strong> \u2014 click to replace';
      }
      updateStatus();
      var savedAccent = profile.accentColor || 'yellow';
      document.querySelectorAll('[data-accent-swatch]').forEach(function (el) {
        var active = el.getAttribute('data-accent-swatch') === savedAccent;
        el.setAttribute('aria-pressed', active ? 'true' : 'false');
        el.style.outline = active ? '2px solid #fff' : '2px solid transparent';
      });
      if ((profile.companyName || '').trim()) {
        fields.style.display = '';
        arrow.innerHTML      = '&#9650;';
      }
    }

    // ── Swatch click handlers ──────────────────────────────────────────────

    document.querySelectorAll('[data-accent-swatch]').forEach(function (swatch) {
      swatch.addEventListener('click', function () {
        document.querySelectorAll('[data-accent-swatch]').forEach(function (el) {
          el.setAttribute('aria-pressed', 'false');
          el.style.outline = '2px solid transparent';
        });
        swatch.setAttribute('aria-pressed', 'true');
        swatch.style.outline = '2px solid #fff';
        save();
      });
    });

    // ── Toggle collapse ────────────────────────────────────────────────────

    header.addEventListener('click', function () {
      var open             = fields.style.display !== 'none';
      fields.style.display = open ? 'none' : '';
      arrow.innerHTML      = open ? '&#9660;' : '&#9650;';
    });

    // ── Text field listeners (auto-save) ───────────────────────────────────

    [companyEl, roleEl, contactEl].forEach(function (el) {
      el.addEventListener('input', save);
    });

    phoneEl.addEventListener('input', function () {
      var raw = phoneEl.value;
      var pos = phoneEl.selectionStart || 0;
      var fmt = formatPhone(raw);
      phoneEl.value = fmt;
      var diff = fmt.length - raw.length;
      try { phoneEl.setSelectionRange(pos + diff, pos + diff); } catch (_) {}
      save();
    });

    // ── Logo upload ────────────────────────────────────────────────────────

    logoInput.addEventListener('change', function () {
      if (!logoInput.files || !logoInput.files.length) return;
      var file = logoInput.files[0];
      fileToBase64(file).then(function (dataUrl) {
        _logoDataUrl = dataUrl;
        logoDrop.classList.add('has-files');
        logoLabel.innerHTML = '<strong>' + escHtml(file.name) + '</strong> \u2014 logo ready';
        if ((companyEl.value || '').trim()) save();
      }).catch(function () {
        logoLabel.innerHTML = '<strong>Click to upload logo</strong>';
      });
    });

    // ── Preset UI ─────────────────────────────────────────────────────────

    renderPresetList(presetList);

    presetSaveBtn.addEventListener('click', function () {
      presetNameInput.value         = '';
      presetNameRow.style.display   = 'flex';
      presetNameInput.focus();
    });

    presetCancel.addEventListener('click', function () {
      presetNameRow.style.display = 'none';
    });

    presetConfirm.addEventListener('click', function () {
      var name    = (presetNameInput.value || '').trim();
      if (!name) { presetNameInput.focus(); return; }
      var profile = readProfileFromFormState(null);
      if (!profile) { presetNameRow.style.display = 'none'; return; }
      saveProfilePreset(name, profile);
      presetNameRow.style.display = 'none';
      renderPresetList(presetList);
    });

    presetNameInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter')  { presetConfirm.click(); }
      if (e.key === 'Escape') { presetCancel.click();  }
    });

    restoreFields();
  }

  // ── Exports ────────────────────────────────────────────────────────────────

  window.getDealerProfile         = getDealerProfile;
  window.initDealerProfile        = initDealerProfile;
  window.readProfileFromFormState = readProfileFromFormState;
  window.writeProfileToFormState  = writeProfileToFormState;
  window.saveProfilePreset        = saveProfilePreset;
  window.loadProfilePresets       = loadProfilePresets;
  window.deleteProfilePreset      = deleteProfilePreset;
  window.formatPhone              = formatPhone;
  window.hydrateProfile           = hydrateProfile;
})();
