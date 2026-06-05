/*
 * Deprecated on purpose.
 *
 * The real novel-to-script conversion now lives in the Python backend:
 *   app/services/adaptation_service.py
 *
 * This file is kept only so older browser caches or open editor tabs do not
 * fail loudly. It does not generate screenplay content and should not be used
 * as an AI conversion engine.
 */

window.NovelScriptBackendOnly = {
  mode: "backend",
  api: "/api/scripts/convert"
};
