/* imagePackExporter.js — stamp photos with dealer badge, return Blob[] (no ZIP) */
(function () {
  'use strict';

  /**
   * exportImagePack(profileOrForm, photos, opts) → Promise<Blob[]>
   *
   * profileOrForm  — dealer profile object, OR a DOM form element (reads form state)
   * photos         — Array of File objects
   * opts           — { onProgress(done, total) }
   *
   * Returns the stamped Blob array. If no profile or no photos, returns the
   * original File array unchanged (File extends Blob, so callers can treat
   * the result uniformly).
   */
  async function exportImagePack(profileOrForm, photos, opts) {
    // Resolve profile
    var profile;
    if (profileOrForm && profileOrForm.nodeType) {
      profile = window.readProfileFromFormState ? window.readProfileFromFormState(profileOrForm) : null;
    } else {
      profile = profileOrForm || null;
    }

    var files = Array.isArray(photos) ? photos.filter(Boolean) : [];
    if (!profile || !files.length) {
      return files;
    }
    var hasAny = (profile.companyName || '').trim() ||
                 (profile.contactName || '').trim() ||
                 (profile.phone       || '').trim() ||
                 profile.logoDataUrl;
    if (!hasAny) {
      return files;
    }

    if (!window.stampPhotoBatch) {
      return files;
    }

    return window.stampPhotoBatch(files, profile, opts && opts.onProgress);
  }

  window.exportImagePack = exportImagePack;
})();
