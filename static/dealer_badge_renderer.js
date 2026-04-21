/* dealer_badge_renderer.js — client-side dealer badge stamping for MTM photo packs */
console.log('>>> DEALER BADGE FILE LOADED');
(function () {
  'use strict';

  var DARK = { bg: '#0D0D0D', text: '#FFFFFF', muted: 'rgba(255,255,255,0.62)', div: '#F5C400', acc: '#F5C400' };

  // ── Helpers ────────────────────────────────────────────────────────────────────

  function trunc(s, n) {
    s = String(s || '');
    return s.length > n ? s.slice(0, n - 1) + '\u2026' : s;
  }

  function loadImage(src) {
    return new Promise(function (res, rej) {
      var img    = new Image();
      img.onload  = function () { res(img); };
      img.onerror = function () { rej(new Error('img load failed: ' + src.slice(0, 40))); };
      img.src     = src;
    });
  }

  function roundRectPath(ctx, x, y, w, h, r) {
    if (ctx.roundRect) { ctx.roundRect(x, y, w, h, r); return; }
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y,     x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x,     y + h, x,     y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x,     y,     x + r, y);
    ctx.closePath();
  }

  // ── Core badge draw (synchronous — all images already loaded) ─────────────────

  function drawBadge(cv, ctx, profile, logoImg, scale) {
    var clr = DARK;

    // Scaled metrics
    var padX     = 12  * scale;
    var padY     = 12  * scale;
    var logoSz   = 40  * scale;
    var gap      = 6   * scale;
    var divW     = 2   * scale;
    var stripeH  = 4   * scale;
    var radius   = 8   * scale;
    var margin   = 16  * scale;
    var lineGap  = 4   * scale;

    // Font sizes
    var roleSize  = 9  * scale;
    var nameSize  = 14 * scale;
    var phoneSize = 11 * scale;

    var roleFont  = '600 ' + roleSize  + "px 'Barlow Condensed','Barlow',sans-serif";
    var nameFont  = '700 ' + nameSize  + "px 'Barlow',sans-serif";
    var phoneFont = '400 ' + phoneSize + "px 'Barlow',sans-serif";

    // Text content
    var contact = (profile.contactName || '').trim();
    var phone   = (profile.phone       || '').trim();
    var role    = (profile.role        || '').trim().toUpperCase();

    var lines = [];
    if (role)    lines.push({ text: role,    sz: roleSize,  font: roleFont,  col: clr.acc  });
    if (contact) lines.push({ text: contact, sz: nameSize,  font: nameFont,  col: clr.text });
    if (phone)   lines.push({ text: phone,   sz: phoneSize, font: phoneFont, col: clr.muted });

    if (lines.length === 0) return;

    // Measure max text width
    var maxW = 100 * scale;
    for (var li = 0; li < lines.length; li++) {
      ctx.font = lines[li].font;
      maxW = Math.max(maxW, ctx.measureText(lines[li].text).width);
    }

    // Content height = sum of line heights + gaps
    var contentH = 0;
    for (var lj = 0; lj < lines.length; lj++) {
      contentH += lines[lj].sz + (lj < lines.length - 1 ? lineGap : 0);
    }

    var badgeH = 2 * padY + Math.max(logoSz, contentH);
    var badgeW = padX + logoSz + gap + divW + gap + maxW + padX;

    var bx = margin;
    var by = cv.height - margin - badgeH;

    // Shadow + rounded background
    ctx.save();
    ctx.shadowColor   = 'rgba(0,0,0,0.5)';
    ctx.shadowBlur    = 12 * scale;
    ctx.shadowOffsetY = 5  * scale;
    ctx.beginPath();
    roundRectPath(ctx, bx, by, badgeW, badgeH, radius);
    ctx.fillStyle = clr.bg;
    ctx.fill();
    ctx.restore();

    // Top yellow accent stripe (clipped to badge rounded corners)
    ctx.save();
    ctx.beginPath();
    roundRectPath(ctx, bx, by, badgeW, badgeH, radius);
    ctx.clip();
    ctx.fillStyle = clr.acc;
    ctx.fillRect(bx, by, badgeW, stripeH);
    ctx.restore();

    // Logo
    var lx = bx + padX;
    var ly = by + (badgeH - logoSz) / 2;
    ctx.drawImage(logoImg, lx, ly, logoSz, logoSz);

    // Vertical divider
    var divX      = bx + padX + logoSz + gap;
    var divTop    = by + padY * 0.6;
    var divHeight = badgeH - padY * 1.2;
    ctx.fillStyle = clr.div;
    ctx.fillRect(divX, divTop, divW, divHeight);

    // Text — vertically centered
    var textX = divX + divW + gap;
    var textY = by + (badgeH - contentH) / 2;

    ctx.save();
    ctx.shadowColor = 'transparent';
    for (var lk = 0; lk < lines.length; lk++) {
      var ln = lines[lk];
      ctx.font      = ln.font;
      ctx.fillStyle = ln.col;
      ctx.fillText(ln.text, textX, textY + ln.sz);
      textY += ln.sz + lineGap;
    }
    ctx.restore();
  }

  // ── Public: render one photo ───────────────────────────────────────────────────

  async function renderDealerBadge(photoFile, dealerProfile) {
    console.log('>>> NEW BADGE RENDERER ACTIVE');
    console.log('renderDealerBadge CALLED', { profile: dealerProfile, source: photoFile && photoFile.name });

    // Apply phone formatting
    var profile = Object.assign({}, dealerProfile);
    if (profile.phone && window.formatPhone) {
      profile.phone = window.formatPhone(profile.phone);
    }

    // No valid logo → return original file unchanged
    var logoImg = null;
    if (profile.logoDataUrl) {
      try { logoImg = await loadImage(profile.logoDataUrl); } catch (_) {}
    }
    if (!logoImg) return photoFile;

    var url   = URL.createObjectURL(photoFile);
    var photo;
    try {
      photo = await loadImage(url);
    } finally {
      URL.revokeObjectURL(url);
    }

    var cv    = document.createElement('canvas');
    cv.width  = photo.naturalWidth;
    cv.height = photo.naturalHeight;
    var ctx   = cv.getContext('2d');
    ctx.drawImage(photo, 0, 0);

    var scale = Math.max(photo.naturalWidth, photo.naturalHeight) / 800;

    drawBadge(cv, ctx, profile, logoImg, scale);

    return new Promise(function (res) { cv.toBlob(res, 'image/jpeg', 0.92); });
  }

  // ── Public: stamp a batch (max 3 concurrent, mobile-safe) ─────────────────────

  async function stampPhotoBatch(files, dealerProfile, onProgress) {
    var MAX     = 3;
    var results = new Array(files.length);
    var next    = 0;

    async function worker() {
      while (next < files.length) {
        var i      = next++;
        results[i] = await renderDealerBadge(files[i], dealerProfile);
        if (onProgress) onProgress(i + 1, files.length);
      }
    }

    var pool = [];
    for (var w = 0; w < Math.min(MAX, files.length); w++) pool.push(worker());
    await Promise.all(pool);
    return results;
  }

  // ── Exports ────────────────────────────────────────────────────────────────────

  window.renderDealerBadge = renderDealerBadge;
  window.stampPhotoBatch   = stampPhotoBatch;
})();
