/* dealer_badge_renderer.js — client-side dealer badge stamping for MTM photo packs */
console.log('>>> DEALER BADGE FILE LOADED');
(function () {
  'use strict';

  // DARK badge: use when logo artwork is light (luminance > 0.7)
  var DARK  = { bg: '#1A1A1A', text: '#FFFFFF', muted: 'rgba(255,255,255,0.62)', div: '#F5A623', acc: '#F5A623', border: false };
  // WHITE badge: use when logo artwork is dark (luminance <= 0.7)
  var WHITE = { bg: '#FFFFFF', text: '#1A1A1A', muted: 'rgba(26,26,26,0.62)',    div: '#F5A623', acc: '#F5A623', border: true  };

  var LUMA_THRESHOLD = 0.7;
  var NEAR_WHITE_CUT = 0.95;
  var MIN_USABLE_PX  = 50;

  // ── Helpers ────────────────────────────────────────────────────────────────────

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

  // ── Theme detection ────────────────────────────────────────────────────────────

  function linearize(c) {
    c = c / 255.0;
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  }

  function pixelLuminance(r, g, b) {
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b);
  }

  function detectLogoTheme(logoImg) {
    var w = logoImg.naturalWidth  || logoImg.width  || 1;
    var h = logoImg.naturalHeight || logoImg.height || 1;
    var cv  = document.createElement('canvas');
    cv.width = w; cv.height = h;
    var ctx = cv.getContext('2d');
    ctx.drawImage(logoImg, 0, 0);
    var data  = ctx.getImageData(0, 0, w, h).data;
    var total = 0, count = 0;
    for (var i = 0; i < data.length; i += 4) {
      if (data[i + 3] <= 10) continue;
      var lum = pixelLuminance(data[i], data[i + 1], data[i + 2]);
      if (lum > NEAR_WHITE_CUT) continue;
      total += lum;
      count++;
    }
    if (count < MIN_USABLE_PX) {
      console.log('[badge-theme] fallback DARK — usable pixels:', count);
      return DARK;
    }
    var avg = total / count;
    var chosen = avg > LUMA_THRESHOLD ? DARK : WHITE;
    console.log('[badge-theme] usable px:', count,
                '| avg lum:', avg.toFixed(4),
                '| theme:', avg > LUMA_THRESHOLD ? 'DARK' : 'WHITE');
    return chosen;
  }

  // ── Logo trim ─────────────────────────────────────────────────────────────────
  // Find the tight bounding box of non-transparent pixels so aspect ratio and
  // drawImage source rect are based on actual artwork, not padded canvas edges.

  function trimLogoBounds(logoImg) {
    var raw_w = logoImg.naturalWidth  || logoImg.width  || 1;
    var raw_h = logoImg.naturalHeight || logoImg.height || 1;
    var cv  = document.createElement('canvas');
    cv.width = raw_w; cv.height = raw_h;
    var ctx = cv.getContext('2d');
    ctx.drawImage(logoImg, 0, 0);
    var data = ctx.getImageData(0, 0, raw_w, raw_h).data;

    var minX = raw_w, maxX = 0, minY = raw_h, maxY = 0, found = false;
    for (var y = 0; y < raw_h; y++) {
      for (var x = 0; x < raw_w; x++) {
        if (data[(y * raw_w + x) * 4 + 3] > 10) {
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
          found = true;
        }
      }
    }

    if (!found) return { x: 0, y: 0, w: raw_w, h: raw_h, raw_w: raw_w, raw_h: raw_h };
    return { x: minX, y: minY, w: maxX - minX + 1, h: maxY - minY + 1, raw_w: raw_w, raw_h: raw_h };
  }

  // ── Core badge draw ────────────────────────────────────────────────────────────
  // All pixel values are in photo canvas space (same coordinate system as cv).

  function drawBadge(cv, ctx, profile, logoImg, clr, trim) {
    var photo_w = cv.width;
    var photo_h = cv.height;

    // ── 1. Badge width ─────────────────────────────────────────────────────────
    var badge_w = Math.min(700, Math.max(400, Math.round(photo_w * 0.45)));

    // ── 2. Logo sizing — trimmed aspect ratio, no square forcing, no crop ──────
    // native_aspect is derived from visible artwork bounds, not raw canvas size
    var native_aspect = trim.w / Math.max(trim.h, 1);
    var logo_h = Math.min(100, Math.max(60, Math.round(photo_w * 0.06)));
    var logo_w = Math.round(logo_h * native_aspect);

    // ── 3. Badge height ────────────────────────────────────────────────────────
    var badge_h = logo_h + 24;  // 12px top + 12px bottom

    // ── 4. Internal layout constants (spec-defined, in photo px) ───────────────
    var padL = 14;
    var padR = 14;
    var padV = 12;
    var gap  = 14;
    var divW = 3;

    // Decorative elements scale with logo_h
    var ps      = logo_h / 90.0;  // proportional scale (1.0 at reference logo_h=90)
    var lineGap = Math.max(3, Math.round(4  * ps));
    var stripeH = Math.max(3, Math.round(4  * ps));
    var radius  = Math.max(4, Math.round(6  * ps));
    var margin  = Math.max(12, Math.round(20 * ps));

    // Font sizes scale with logo_h
    var roleSize  = Math.max(8,  Math.round(12 * ps));
    var nameSize  = Math.max(9,  Math.round(18 * ps));
    var phoneSize = Math.max(8,  Math.round(14 * ps));

    var roleFont  = '600 ' + roleSize  + "px 'Barlow Condensed','Barlow',sans-serif";
    var nameFont  = '700 ' + nameSize  + "px 'Barlow',sans-serif";
    var phoneFont = '400 ' + phoneSize + "px 'Barlow',sans-serif";

    // ── Build text lines ───────────────────────────────────────────────────────
    var contact = (profile.contactName || '').trim();
    var phone   = (profile.phone       || '').trim();
    var role    = (profile.role        || '').trim().toUpperCase();

    var lines = [];
    if (role)    lines.push({ text: role,    sz: roleSize,  font: roleFont,  col: clr.acc   });
    if (contact) lines.push({ text: contact, sz: nameSize,  font: nameFont,  col: clr.text  });
    if (phone)   lines.push({ text: phone,   sz: phoneSize, font: phoneFont, col: clr.muted });

    if (lines.length === 0) return;

    // ── Measure text and handle overflow ───────────────────────────────────────

    ctx.save();
    var maxTextW = 0;
    for (var li = 0; li < lines.length; li++) {
      ctx.font = lines[li].font;
      maxTextW = Math.max(maxTextW, ctx.measureText(lines[li].text).width);
    }
    ctx.restore();

    // Step 1: expand badge width if content needs more room (logo drives width, not text)
    var required_w = padL + logo_w + gap + divW + gap + maxTextW + padR;
    if (required_w > badge_w) {
      badge_w = Math.min(700, Math.ceil(required_w));
    }

    // Step 2: if at max width and text still overflows, shrink text proportionally.
    // Logo is not touched — it shrinks last only if logo itself is the cause of overflow.
    var avail_text_w = badge_w - padL - logo_w - gap - divW - gap - padR;
    if (avail_text_w > 0 && maxTextW > avail_text_w) {
      var shrink = avail_text_w / maxTextW;
      lines = lines.map(function (ln) {
        var newSz  = Math.max(8, Math.round(ln.sz * shrink));
        var newFont = ln.font.replace(/\d+px/, newSz + 'px');
        return { text: ln.text, sz: newSz, font: newFont, col: ln.col };
      });
    }

    // Step 3: if even at 700px the logo alone overflows, shrink logo proportionally
    var fixed_chrome = padL + gap + divW + gap + 40 + padR;  // 40px minimum text area
    if (logo_w > 700 - fixed_chrome) {
      logo_w = Math.max(60, 700 - fixed_chrome);
      logo_h = Math.round(logo_w / native_aspect);
      badge_h = logo_h + 24;
    }

    // ── 6. Debug output ────────────────────────────────────────────────────────
    var raw_aspect     = trim.raw_w / Math.max(trim.raw_h, 1);
    var trim_area_pct  = (1 - (trim.w * trim.h) / (trim.raw_w * trim.raw_h)) * 100;
    console.log('[badge-size]', {
      source_photo_width:  photo_w,
      computed_badge_w:    badge_w,
      computed_badge_h:    badge_h,
      logo_render:         logo_w + 'x' + logo_h,
      logo_raw_dims:       trim.raw_w + 'x' + trim.raw_h,
      logo_trimmed_dims:   trim.w + 'x' + trim.h,
      raw_aspect:          raw_aspect.toFixed(3),
      trimmed_aspect:      native_aspect.toFixed(3),
      padding_removed_pct: trim_area_pct.toFixed(1) + '%',
      badge_pct_of_photo:  (badge_w / photo_w * 100).toFixed(1) + '%',
    });

    // ── Draw badge ─────────────────────────────────────────────────────────────
    var bx = margin;
    var by = photo_h - margin - badge_h;

    // Shadow + background
    ctx.save();
    ctx.shadowColor   = 'rgba(0,0,0,0.35)';
    ctx.shadowBlur    = Math.round(10 * ps);
    ctx.shadowOffsetY = Math.round(3  * ps);
    ctx.beginPath();
    roundRectPath(ctx, bx, by, badge_w, badge_h, radius);
    ctx.fillStyle = clr.bg;
    ctx.fill();
    ctx.restore();

    // Border (WHITE badge only)
    if (clr.border) {
      ctx.save();
      ctx.beginPath();
      roundRectPath(ctx, bx, by, badge_w, badge_h, radius);
      ctx.strokeStyle = '#1A1A1A';
      ctx.lineWidth   = Math.max(1, 1.5 * ps);
      ctx.stroke();
      ctx.restore();
    }

    // Top accent stripe (clipped to rounded corners)
    ctx.save();
    ctx.beginPath();
    roundRectPath(ctx, bx, by, badge_w, badge_h, radius);
    ctx.clip();
    ctx.fillStyle = clr.acc;
    ctx.fillRect(bx, by, badge_w, stripeH);
    ctx.restore();

    // Logo — draw only the trimmed visible region, scaled to target render size
    var lx = bx + padL;
    var ly = by + padV;
    ctx.drawImage(logoImg, trim.x, trim.y, trim.w, trim.h, lx, ly, logo_w, logo_h);

    // Vertical divider
    var divX = lx + logo_w + gap;
    ctx.fillStyle = clr.div;
    ctx.fillRect(divX, by + padV * 0.667, divW, badge_h - padV * 1.333);

    // Text stack — left aligned, vertically centered in badge height
    var textX    = divX + divW + gap;
    var contentH = 0;
    for (var lj = 0; lj < lines.length; lj++) {
      contentH += lines[lj].sz + (lj < lines.length - 1 ? lineGap : 0);
    }
    var textY = by + (badge_h - contentH) / 2;

    ctx.save();
    ctx.shadowColor = 'transparent';
    for (var lk = 0; lk < lines.length; lk++) {
      ctx.font      = lines[lk].font;
      ctx.fillStyle = lines[lk].col;
      ctx.fillText(lines[lk].text, textX, textY + lines[lk].sz);
      textY += lines[lk].sz + lineGap;
    }
    ctx.restore();
  }

  // ── Public: render one photo ───────────────────────────────────────────────────

  async function renderDealerBadge(photoFile, dealerProfile) {
    console.log('>>> NEW BADGE RENDERER ACTIVE');

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

    // Theme and trim — both derived from pixel data, not filename or metadata
    var clr  = detectLogoTheme(logoImg);
    var trim = trimLogoBounds(logoImg);

    var url = URL.createObjectURL(photoFile);
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

    drawBadge(cv, ctx, profile, logoImg, clr, trim);

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
