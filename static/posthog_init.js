// MTM PostHog initialization + tracking helper.
// Loads posthog-js from cdn and exposes window.mtmTrack(event, props).
// Replace POSTHOG_KEY below with the project API key from the PostHog UI.
(function () {
  var POSTHOG_KEY = (window.MTM_POSTHOG_KEY || "phc_REPLACE_WITH_YOUR_PROJECT_KEY");
  var POSTHOG_HOST = (window.MTM_POSTHOG_HOST || "https://us.i.posthog.com");

  // Standard PostHog JS snippet (array.js loader).
  !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing startSessionRecording stopSessionRecording sessionRecordingStarted captureException loadToolbar get_property getSessionProperty createPersonProfile opt_in_session_recording opt_out_session_recording has_opted_in_session_recording has_opted_out_session_recording clear_opt_in_out_session_recording".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);

  try {
    posthog.init(POSTHOG_KEY, {
      api_host: POSTHOG_HOST,
      person_profiles: "identified_only",
      capture_pageview: true,
    });
  } catch (e) { /* swallow — never break the page */ }

  // Safe wrapper used by all template event hooks.
  window.mtmTrack = function (event, props) {
    try {
      if (window.posthog && typeof posthog.capture === "function") {
        posthog.capture(event, props || {});
      }
    } catch (e) { /* no-op */ }
  };
})();
