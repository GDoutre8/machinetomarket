/* dealer_profile.js — dealer badge profile UI + localStorage persistence */
(function () {
  'use strict';

  var STORAGE_KEY = 'mtm_dealer_profile';

  // ── Storage ────────────────────────────────────────────────────────────────────

  function getDealerProfile() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) { return null; }
  }

  function saveDealerProfileData(profile) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(profile)); } catch (_) {}
  }

  // ── Phone auto-format: (###) ###-#### ─────────────────────────────────────────

  function formatPhone(raw) {
    var digits = raw.replace(/\D/g, '').slice(0, 10);
    if (digits.length >= 7) return '(' + digits.slice(0, 3) + ') ' + digits.slice(3, 6) + '-' + digits.slice(6);
    if (digits.length >= 4) return '(' + digits.slice(0, 3) + ') ' + digits.slice(3);
    if (digits.length >= 1) return '(' + digits;
    return '';
  }

  function fileToBase64(file) {
    return new Promise(function (res, rej) {
      var reader      = new FileReader();
      reader.onload   = function (e) { res(e.target.result); };
      reader.onerror  = rej;
      reader.readAsDataURL(file);
    });
  }

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── UI init ────────────────────────────────────────────────────────────────────

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
        '<div style="font-size:11px;color:var(--dim);">Changes save automatically.</div>',
      '</div>',
    ].join('');

    var header    = document.getElementById('dp-header');
    var fields    = document.getElementById('dp-fields');
    var arrow     = document.getElementById('dp-arrow');
    var statusEl  = document.getElementById('dp-status');
    var companyEl = document.getElementById('dp-company');
    var roleEl    = document.getElementById('dp-role');
    var contactEl = document.getElementById('dp-contact');
    var phoneEl   = document.getElementById('dp-phone');
    var logoInput = document.getElementById('dp-logo-input');
    var logoLabel = document.getElementById('dp-logo-label');
    var logoDrop  = document.getElementById('dp-logo-drop');

    var currentLogoDataUrl = null;

    // ── Status indicator ───────────────────────────────────────────────────────

    function updateStatus() {
      var hasProfile = !!(companyEl.value || '').trim();
      statusEl.textContent = hasProfile ? '\u2014 Badge Active' : '\u2014 No Profile (badge off)';
      statusEl.style.color = hasProfile ? '#5cc58a' : 'var(--dim)';
    }

    // ── Save to localStorage ───────────────────────────────────────────────────

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
        logoDataUrl:  currentLogoDataUrl,
      });
      updateStatus();
    }

    // ── Restore from localStorage ──────────────────────────────────────────────

    function restoreFields() {
      var profile = getDealerProfile();
      if (!profile) { updateStatus(); return; }
      companyEl.value = profile.companyName  || '';
      roleEl.value    = profile.role         || '';
      contactEl.value = profile.contactName  || '';
      phoneEl.value   = profile.phone        || '';
      if (profile.logoDataUrl) {
        currentLogoDataUrl = profile.logoDataUrl;
        logoDrop.classList.add('has-files');
        logoLabel.innerHTML = '<strong>Logo loaded</strong> \u2014 click to replace';
      }
      updateStatus();
      // Auto-expand when a profile is already set
      if ((profile.companyName || '').trim()) {
        fields.style.display = '';
        arrow.innerHTML      = '&#9650;';
      }
    }

    // ── Toggle collapse ────────────────────────────────────────────────────────

    header.addEventListener('click', function () {
      var open         = fields.style.display !== 'none';
      fields.style.display = open ? 'none' : '';
      arrow.innerHTML  = open ? '&#9660;' : '&#9650;';
    });

    // ── Text field listeners (auto-save) ───────────────────────────────────────

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

    // ── Logo upload ────────────────────────────────────────────────────────────

    logoInput.addEventListener('change', function () {
      if (!logoInput.files || !logoInput.files.length) return;
      var file = logoInput.files[0];
      fileToBase64(file).then(function (dataUrl) {
        currentLogoDataUrl = dataUrl;
        logoDrop.classList.add('has-files');
        logoLabel.innerHTML = '<strong>' + escHtml(file.name) + '</strong> \u2014 logo ready';
        if ((companyEl.value || '').trim()) save();
      }).catch(function () {
        logoLabel.innerHTML = '<strong>Click to upload logo</strong>';
      });
    });

    restoreFields();
  }

  // ── Exports ────────────────────────────────────────────────────────────────────

  window.getDealerProfile  = getDealerProfile;
  window.initDealerProfile = initDealerProfile;
})();
