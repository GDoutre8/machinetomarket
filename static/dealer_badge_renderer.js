/* dealer_badge_renderer.js — client-side dealer badge stamping for MTM photo packs */
(function () {
  'use strict';

  var DARK  = { bg: '#1A1A1A', text: '#FFFFFF', muted: 'rgba(255,255,255,0.62)', div: '#F5C400', acc: '#F5C400' };
  var LIGHT = { bg: '#FFFFFF', text: '#111111', muted: 'rgba(17,17,17,0.62)',    div: '#CC2222', acc: '#CC2222' };

  // ── Logo white-detection ───────────────────────────────────────────────────────
  // Sample 8×8px from each corner; return true if avg brightness of opaque pixels > 200

  function detectWhiteLogo(img) {
    var size = 8;
    var cv   = document.createElement('canvas');
    var w    = img.naturalWidth  || img.width  || 1;
    var h    = img.naturalHeight || img.height || 1;
    cv.width = w; cv.height = h;
    var ctx  = cv.getContext('2d');
    ctx.drawImage(img, 0, 0);
    var corners = [[0, 0], [w - size, 0], [0, h - size], [w - size, h - size]];
    var total = 0, count = 0;
    for (var ci = 0; ci < corners.length; ci++) {
      var cx = corners[ci][0], cy = corners[ci][1];
      var d  = ctx.getImageData(Math.max(0, cx), Math.max(0, cy), size, size).data;
      for (var i = 0; i < d.length; i += 4) {
        if (d[i + 3] > 10) { total += (d[i] + d[i + 1] + d[i + 2]) / 3; count++; }
      }
    }
    return count > 0 && (total / count) > 200;
  }

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
    var isWhite = logoImg ? detectWhiteLogo(logoImg) : false;
    var clr     = isWhite ? LIGHT : DARK;
    var hasLogo = !!logoImg;

    // Scaled metrics
    var padX   = 12  * scale;
    var padY   = 12  * scale;
    var logoSz = 40  * scale;
    var gap    = 6   * scale;
    var divW   = 2   * scale;
    var barW   = 2.5 * scale;
    var radius = 8   * scale;
    var margin = 16  * scale;
    var lineGap= 4   * scale;

    // Font sizes
    var roleSize  = 9  * scale;
    var nameSize  = 14 * scale;
    var phoneSize = 11 * scale;

    var roleFont  = '600 ' + roleSize  + "px 'Barlow Condensed','Barlow',sans-serif";
    var nameFont  = '700 ' + nameSize  + "px 'Barlow',sans-serif";
    var phoneFont = '400 ' + phoneSize + "px 'Barlow',sans-serif";

    // Text content
    var company = trunc(profile.companyName || '', 22).toUpperCase();
    var contact = (profile.contactName || '').trim();
    var phone   = (profile.phone       || '').trim();
    var role    = (profile.role        || '').trim().toUpperCase();

    // Build lines array
    var lines = [];
    if (hasLogo) {
      if (role)    lines.push({ text: role,    sz: roleSize,  font: roleFont,  col: clr.acc  });
      if (contact) lines.push({ text: contact, sz: nameSize,  font: nameFont,  col: clr.text });
      if (phone)   lines.push({ text: phone,   sz: phoneSize, font: phoneFont, col: clr.muted });
    } else {
      // No logo: company name on the role line per spec
      if (company) lines.push({ text: company, sz: roleSize,  font: roleFont,  col: clr.acc  });
      if (contact) lines.push({ text: contact, sz: nameSize,  font: nameFont,  col: clr.text });
      if (phone)   lines.push({ text: phone,   sz: phoneSize, font: phoneFont, col: clr.muted });
    }

    if (lines.length === 0) return; // nothing to draw

    // Measure max text width
    var maxW = 100 * scale; // minimum text block width
    for (var li = 0; li < lines.length; li++) {
      ctx.font = lines[li].font;
      maxW = Math.max(maxW, ctx.measureText(lines[li].text).width);
    }

    // Content height = sum of line heights + gaps between lines
    var contentH = 0;
    for (var lj = 0; lj < lines.length; lj++) {
      contentH += lines[lj].sz + (lj < lines.length - 1 ? lineGap : 0);
    }

    var badgeH = 2 * padY + Math.max(hasLogo ? logoSz : 0, contentH);
    var badgeW = hasLogo
      ? padX + logoSz + gap + divW + gap + maxW + padX
      : padX + barW   + gap + maxW + padX;

    var bx = margin;
    var by = cv.height - margin - badgeH;

    // Shadow + rounded background
    ctx.save();
    ctx.shadowColor   = 'rgba(0,0,0,0.5)';
    ctx.shadowBlur    = 14 * scale;
    ctx.shadowOffsetY = 3  * scale;
    ctx.beginPath();
    roundRectPath(ctx, bx, by, badgeW, badgeH, radius);
    ctx.fillStyle = clr.bg;
    ctx.fill();

    if (isWhite) {
      // Light badge: add subtle border (after clearing shadow)
      ctx.shadowColor = 'transparent';
      ctx.strokeStyle = 'rgba(0,0,0,0.1)';
      ctx.lineWidth   = 0.5 * scale;
      ctx.stroke();
    }
    ctx.restore();

    // Logo or accent bar
    var accentTop    = by + padY * 0.6;
    var accentHeight = badgeH - padY * 1.2;
    if (hasLogo) {
      var lx = bx + padX;
      var ly = by + (badgeH - logoSz) / 2;
      ctx.drawImage(logoImg, lx, ly, logoSz, logoSz);
      // Vertical divider
      ctx.fillStyle = clr.div;
      ctx.fillRect(bx + padX + logoSz + gap, accentTop, divW, accentHeight);
    } else {
      // Accent bar flush left of text
      ctx.fillStyle = clr.acc;
      ctx.fillRect(bx + padX, accentTop, barW, accentHeight);
    }

    // Text — vertically centered in badge content area
    var textX = hasLogo
      ? bx + padX + logoSz + gap + divW + gap
      : bx + padX + barW + gap;
    var textY = by + (badgeH - contentH) / 2;

    ctx.save();
    ctx.shadowColor = 'transparent';
    for (var lk = 0; lk < lines.length; lk++) {
      var ln = lines[lk];
      ctx.font      = ln.font;
      ctx.fillStyle = ln.col;
      ctx.fillText(ln.text, textX, textY + ln.sz); // +sz: top-of-line → baseline
      textY += ln.sz + lineGap;
    }
    ctx.restore();
  }

  // ── Public: render one photo ───────────────────────────────────────────────────

  async function renderDealerBadge(photoFile, dealerProfile) {
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

    var scale   = Math.max(photo.naturalWidth, photo.naturalHeight) / 800;
    var logoImg = null;
    if (dealerProfile.logoDataUrl) {
      try { logoImg = await loadImage(dealerProfile.logoDataUrl); } catch (_) {}
    }

    drawBadge(cv, ctx, dealerProfile, logoImg, scale);

    return new Promise(function (res) { cv.toBlob(res, 'image/jpeg', 0.92); });
  }

  // ── Public: stamp a batch (max 3 concurrent, mobile-safe) ─────────────────────

  async function stampPhotoBatch(files, dealerProfile, onProgress) {
    var MAX     = 3;
    var results = new Array(files.length);
    var next    = 0;

    async function worker() {
      while (next < files.length) {
        var i    = next++;
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
