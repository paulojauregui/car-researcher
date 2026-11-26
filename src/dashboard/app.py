"""
Async Web Dashboard Controller, HTTP router, and v2 Market Intelligence JSON API.

Implements Milestone M04: a zero-dependency asyncio HTTP/ASGI-style router that
serves the SSR dashboard, HTMX partials, safe static assets, and the quantitative
market-intelligence JSON surface backed by ``src.dashboard.queries``.

Pre-conditions:
    - Python standard library only (plus ``src.dashboard.*``, ``src.config.settings``,
      and ``src.workflows.temporal_compat``); no third-party web framework is required.
    - ``DashboardRepository`` is importable and exposes the analytics query layer.
    - Optional Temporal SDK presence is signalled by ``HAS_TEMPORAL``.

Post-conditions:
    - ``DashboardApp.handle_request(method, path, query_params=None, body_params=None,
      headers=None)`` routes every documented endpoint and returns
      ``(status_code, headers_dict, body_bytes)``.
    - Static assets are served only from ``STATIC_DIR`` with traversal-safe resolution.
    - Strictly zero emojis and zero hardcoded Temporal UI hosts across this module.
"""

import asyncio
import html
import inspect
import json
import logging
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config.settings import settings
from src.workflows.temporal_compat import HAS_TEMPORAL
from src.dashboard.queries import DashboardRepository
from src.dashboard.templates import (
    render_full_dashboard_page,
    render_deals_section,
    render_kpis_partial,
    render_listing_history_modal,
    render_model_profile_modal,
    render_scan_status_banner,
)

logger = logging.getLogger(__name__)

STATIC_DIR: Path = Path(__file__).resolve().parent / "static"

CONTENT_TYPE_JSON: str = "application/json"
CONTENT_TYPE_HTML: str = "text/html; charset=utf-8"
CONTENT_TYPE_TEXT: str = "text/plain; charset=utf-8"

MAX_COMPARE_IDS: int = 3
STATIC_PREFIX: str = "/static/"

_STATIC_MIME_TYPES: Dict[str, str] = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}

_HTTP_STATUS_TEXTS: Dict[int, str] = {
    200: "OK",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    500: "Internal Server Error",
}

_FLAG_KEY_ALIASES: Dict[str, str] = {
    "bookmark": "user_bookmarked",
    "dismiss": "user_dismissed",
    "user_bookmarked": "user_bookmarked",
    "user_dismissed": "user_dismissed",
}


def _parse_int(val: Optional[str]) -> Optional[int]:
    """
    Coerce an optional query/form string into an integer.

    Pre-conditions:
        - val is None or a string-ish scalar.

    Post-conditions:
        - Returns the parsed integer, or None for empty or non-numeric inputs.
    """
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _parse_float(val: Optional[str]) -> Optional[float]:
    """
    Coerce an optional query/form string into a float.

    Pre-conditions:
        - val is None or a string-ish scalar.

    Post-conditions:
        - Returns the parsed float, or None for empty or non-numeric inputs.
    """
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _wants_json(
    query_params: Optional[Dict[str, str]],
    headers: Optional[Dict[str, str]],
) -> bool:
    """
    Determine whether the client requested a JSON representation.

    Pre-conditions:
        - query_params is None or a string map of query parameters.
        - headers is None or a map of already lowercased HTTP header names to values.

    Post-conditions:
        - Returns True when ``?format=json`` is present or the ``accept`` header
          mentions ``application/json``; otherwise False.
    """
    q_params = query_params or {}
    req_headers = headers or {}
    if str(q_params.get("format", "")).lower() == "json":
        return True
    accept = str(req_headers.get("accept", "") or "").lower()
    return "application/json" in accept


def _wants_html(query_params: Optional[Dict[str, str]], headers: Optional[Dict[str, str]]) -> bool:
    """
    Determine whether the client explicitly requested an HTML fragment.

    Pre-conditions:
        - query_params is None or a string map of query parameters.
        - headers is None or a map of already lowercased HTTP header names to values.

    Post-conditions:
        - Returns True only when ``?format=html`` is set or the ``accept`` header
          prefers ``text/html`` without also asking for JSON.
    """
    q_params = query_params or {}
    req_headers = headers or {}
    if str(q_params.get("format", "")).lower() == "html":
        return True
    if _wants_json(q_params, req_headers):
        return False
    accept = str(req_headers.get("accept", "") or "").lower()
    return "text/html" in accept


def _json_response(payload: Any, status: int = 200) -> Tuple[int, Dict[str, str], bytes]:
    """
    Build a JSON HTTP response tuple.

    Pre-conditions:
        - payload is JSON serializable (fallback to ``str`` for exotic types such as dates).
        - status is a valid HTTP status code.

    Post-conditions:
        - Returns ``(status, {"Content-Type": "application/json"}, utf-8 body bytes)``.
    """
    body = json.dumps(payload, default=str)
    return status, {"Content-Type": CONTENT_TYPE_JSON}, body.encode("utf-8")


def _html_response(html_text: str, status: int = 200) -> Tuple[int, Dict[str, str], bytes]:
    """
    Build an HTML HTTP response tuple.

    Pre-conditions:
        - html_text is a rendered HTML fragment or document string.
        - status is a valid HTTP status code.

    Post-conditions:
        - Returns ``(status, {"Content-Type": "text/html; charset=utf-8"}, utf-8 body bytes)``.
    """
    return status, {"Content-Type": CONTENT_TYPE_HTML}, html_text.encode("utf-8")


def _text_response(status: int, message: str) -> Tuple[int, Dict[str, str], bytes]:
    """
    Build a plain-text HTTP response tuple.

    Pre-conditions:
        - status is a valid HTTP status code.
        - message is the plain-text body.

    Post-conditions:
        - Returns ``(status, {"Content-Type": "text/plain; charset=utf-8"}, utf-8 body bytes)``.
    """
    return status, {"Content-Type": CONTENT_TYPE_TEXT}, message.encode("utf-8")


def _scan_error_banner(error: Optional[str]) -> str:
    """
    Render the scan failure banner used when a Temporal workflow cannot be started.

    Pre-conditions:
        - error is None or a human-readable failure description.

    Post-conditions:
        - Returns an escaped, emoji-free HTML alert fragment.
    """
    safe_error = html.escape(str(error or "unknown error"))
    return (
        '<div class="scan-error-alert" '
        f'role="alert">Could not trigger scan: {safe_error}</div>'
    )


class DashboardApp:
    """
    Async Web Dashboard Controller and HTTP/ASGI-style request router.

    Supports zero-dependency unit testing (direct ``handle_request`` calls) and native
    asyncio serving inside Docker via :func:`start_dashboard_server`.

    Pre-conditions:
        - repo is None or a ``DashboardRepository``-compatible object exposing the
          analytics query methods used by this router.

    Post-conditions:
        - All documented v1 HTML/HTMX routes and v2 JSON market-intelligence routes
          resolve through a single :meth:`handle_request` entry point.
        - ``self._last_scan_workflow_id`` tracks the most recently started scan.
    """

    def __init__(self, repo: Optional[DashboardRepository] = None) -> None:
        """
        Initialize the dashboard controller.

        Pre-conditions:
            - repo is None (auto-instantiate ``DashboardRepository``) or a repository instance.

        Post-conditions:
            - ``self.repo`` is set and ``self._last_scan_workflow_id`` is None.
        """
        self.repo = repo or DashboardRepository()
        self._last_scan_workflow_id: Optional[str] = None

    @staticmethod
    def _stringify_params(params: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """
        Flatten scalar query/body parameters into a string map.

        Pre-conditions:
            - params is None or a mapping of parameter names to arbitrary decoded values.

        Post-conditions:
            - Returns a new map containing only scalar (str/int/float/bool) values coerced to str;
              nested containers are dropped so filter parsing stays safe.
        """
        flat: Dict[str, str] = {}
        for key, value in (params or {}).items():
            if isinstance(value, (str, int, float, bool)):
                flat[str(key)] = str(value)
        return flat

    @staticmethod
    def _extract_filters(params: Dict[str, str]) -> Dict[str, Any]:
        """
        Translate raw request parameters into the canonical dashboard filter contract.

        Pre-conditions:
            - params is a string map of query/body parameters.

        Post-conditions:
            - Returns a filter dictionary with tab, view, make_filter, q, max_price,
              max_mileage, max_distance, and sort keys using dashboard defaults.
        """
        return {
            "tab": params.get("tab", "all") or "all",
            "view": params.get("view", "grid") or "grid",
            "make_filter": params.get("make", "") or "",
            "q": params.get("q", "") or "",
            "max_price": _parse_int(params.get("max_price")),
            "max_mileage": _parse_int(params.get("max_mileage")),
            "max_distance": _parse_float(params.get("max_distance")),
            "sort": params.get("sort", "score_desc") or "score_desc",
        }

    async def _get_filtered_state(
        self,
        params: Dict[str, str],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        """
        Fetch, enrich, filter, and sort the active deal inventory for a request.

        Pre-conditions:
            - params is a string map of request parameters.

        Post-conditions:
            - Returns ``(filtered_deals, kpis, filters)`` derived from the repository.
        """
        filters = self._extract_filters(params)
        all_deals = await self.repo.fetch_all_Normalized_deals()
        kpis = self.repo.compute_kpis(all_deals)
        filtered = self.repo.filter_and_sort_deals(
            all_deals,
            tab=filters["tab"],
            make_filter=filters["make_filter"],
            search_query=filters["q"],
            max_price=filters["max_price"],
            max_mileage=filters["max_mileage"],
            max_distance=filters["max_distance"],
            sort_by=filters["sort"],
        )
        return filtered, kpis, filters

    async def _render_full_page(
        self,
        deals: List[Dict[str, Any]],
        kpis: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> str:
        """
        Render the full SSR dashboard page with forward-compatible arguments.

        Pre-conditions:
            - deals, kpis, and filters follow the dashboard rendering contract.

        Post-conditions:
            - Returns the rendered HTML document.
            - ``provenance`` is passed when the installed ``render_full_dashboard_page``
              signature declares it.
            - Avoids redundant ``get_market_overview()`` queries and payload duplication
              during synchronous root SSR rendering since the Market Intelligence
              workspace lazy-loads ``/api/market/overview`` on demand.
        """
        try:
            render_params = inspect.signature(render_full_dashboard_page).parameters
        except (TypeError, ValueError):
            render_params = {}

        kwargs: Dict[str, Any] = {}
        if "provenance" in render_params:
            kwargs["provenance"] = self.repo.get_provenance()

        return render_full_dashboard_page(deals, kpis, filters, **kwargs)

    async def trigger_scan_workflow(self, target_spec: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Trigger a Temporal ``DailyCarResearchPipelineWorkflow`` run from the dashboard.

        Pre-conditions:
            - target_spec is a non-empty target descriptor ("ALL" or ``"Make|Model"``).

        Post-conditions:
            - Returns ``(workflow_id, None)`` on success, or ``(None, error_message)`` when
              Temporal is unavailable or the client call fails. Never raises.
        """
        if not HAS_TEMPORAL:
            return None, "Temporal SDK not installed in this environment."

        try:
            from temporalio.client import Client
            from src.workflows.daily_pipeline import DailyCarResearchPipelineWorkflow

            custom_targets = None
            if target_spec and target_spec != "ALL" and "|" in target_spec:
                make, model = target_spec.split("|", 1)
                custom_targets = [{"make": make.strip(), "model": model.strip(), "min_year": 2022}]

            client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
            workflow_id = f"dashboard-scan-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            await client.start_workflow(
                DailyCarResearchPipelineWorkflow.run,
                args=[custom_targets, settings.search_zip_code, settings.search_radius_miles],
                id=workflow_id,
                task_queue=settings.temporal_task_queue_default,
            )
            return workflow_id, None
        except Exception as e:
            logger.error(f"Dashboard failed to start Temporal scan: {e}")
            return None, str(e)

    async def query_scan_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Query a running or completed Temporal workflow for real-time progress.

        Pre-conditions:
            - workflow_id is a non-empty workflow identifier string.

        Post-conditions:
            - Returns a progress summary dictionary with is_completed, total_scraped,
              total_scored, and top_deals_count keys. Never raises.
        """
        if not HAS_TEMPORAL:
            return {"is_completed": True, "total_scraped": 0, "total_scored": 0, "top_deals_count": 0}

        try:
            from temporalio.client import Client
            client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
            handle = client.get_workflow_handle(workflow_id)
            try:
                summary = await handle.query("get_summary")
                return summary
            except Exception:
                desc = await handle.describe()
                is_done = desc.status is not None and int(desc.status) != 1
                return {"is_completed": is_done, "total_scraped": 0, "total_scored": 0, "top_deals_count": 0}
        except Exception as e:
            logger.warning(f"Failed to query workflow {workflow_id}: {e}")
            return {"is_completed": True, "total_scraped": 0, "total_scored": 0, "top_deals_count": 0}

    def _serve_static(self, method: str, clean_path: str) -> Optional[Tuple[int, Dict[str, str], bytes]]:
        """
        Serve a file from ``STATIC_DIR`` for ``/static/<rel_path>`` requests.

        Pre-conditions:
            - method is an uppercase HTTP verb (typically GET or HEAD).
            - clean_path is the normalized, trailing-slash-stripped request path.

        Post-conditions:
            - Returns None when clean_path is not a static asset request.
            - Returns 403 Forbidden for null bytes, empty or absolute relative paths,
              backslashes, dot segments, or any resolved target outside ``STATIC_DIR``.
            - Returns 404 Not Found when the target is missing or is not a regular file.
            - Returns 200 with ``Cache-Control: no-cache`` and a MIME-typed body for GET;
              HEAD responses keep identical headers with an empty body.
        """
        if method not in ("GET", "HEAD"):
            return None
        if clean_path != "/static" and not clean_path.startswith(STATIC_PREFIX):
            return None

        raw_rel = clean_path[len(STATIC_PREFIX):] if clean_path.startswith(STATIC_PREFIX) else ""
        rel_path = urllib.parse.unquote(raw_rel)

        if not rel_path or "\x00" in rel_path or rel_path.startswith("/") or "\\" in rel_path:
            return _text_response(403, "Forbidden")
        if any(segment in ("", ".", "..") for segment in rel_path.split("/")):
            return _text_response(403, "Forbidden")

        try:
            static_root = STATIC_DIR.resolve()
            resolved = (STATIC_DIR / rel_path).resolve()
        except (OSError, ValueError):
            return _text_response(403, "Forbidden")

        if not resolved.is_relative_to(static_root):
            return _text_response(403, "Forbidden")
        if not resolved.is_file():
            return _text_response(404, "Not Found")

        try:
            payload = resolved.read_bytes()
        except OSError:
            return _text_response(404, "Not Found")

        headers = {
            "Content-Type": _STATIC_MIME_TYPES.get(resolved.suffix.lower(), "application/octet-stream"),
            "Cache-Control": "no-cache",
        }
        if method == "HEAD":
            payload = b""
        return 200, headers, payload

    async def _toggle_flag_response(
        self,
        listing_id: str,
        flag_key: str,
        q_params: Dict[str, str],
        headers: Optional[Dict[str, str]],
        merged_params: Dict[str, str],
        force_json: bool = False,
    ) -> Tuple[int, Dict[str, str], bytes]:
        """
        Toggle a user flag and render the negotiated JSON or legacy HTML representation.

        Pre-conditions:
            - listing_id is a non-empty identifier.
            - flag_key is ``user_bookmarked`` or ``user_dismissed``.
            - merged_params already combines query and body filters for the deals section.
            - force_json determines if JSON must be returned regardless of Accept headers.

        Post-conditions:
            - JSON clients receive 200 with ``{id, flag, value, kpis}``, or 404 JSON when
              the listing cannot be found.
            - HTML clients keep the exact v1 contract: 200 with ``render_deals_section`` output.
        """
        new_val = await self.repo.toggle_user_flag(listing_id, flag_key)
        wants_json = force_json or _wants_json(q_params, headers)

        if wants_json and new_val is None:
            return _json_response(
                {"error": "Listing not found", "id": listing_id, "flag": flag_key},
                status=404,
            )

        deals, kpis, filters = await self._get_filtered_state(merged_params)
        if wants_json:
            return _json_response({"id": listing_id, "flag": flag_key, "value": new_val, "kpis": kpis})
        return _html_response(render_deals_section(deals, kpis, filters))

    async def _scan_status_payload(self, workflow_id: Optional[str]) -> Dict[str, Any]:
        """
        Assemble the scan status JSON payload for a workflow identifier.

        Pre-conditions:
            - workflow_id is None or a Temporal workflow identifier string.

        Post-conditions:
            - Returns a dictionary with temporal_available, temporal_ui_url,
              active_workflow_id, and summary (None when no workflow is tracked).
        """
        summary: Optional[Dict[str, Any]] = None
        if workflow_id:
            summary = await self.query_scan_workflow(workflow_id)
        return {
            "temporal_available": bool(HAS_TEMPORAL),
            "temporal_ui_url": settings.temporal_ui_url,
            "active_workflow_id": workflow_id,
            "summary": summary,
        }

    async def handle_request(
        self,
        method: str,
        path: str,
        query_params: Optional[Dict[str, str]] = None,
        body_params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, Dict[str, str], bytes]:
        """
        Route an HTTP request and return ``(status_code, headers_dict, body_bytes)``.

        Pre-conditions:
            - method is an uppercase HTTP verb.
            - path is a URL path (query string already stripped).
            - query_params and body_params are optional mappings; body_params may carry
              decoded JSON payloads (nested containers allowed).
            - headers is an optional map of lowercased header names to values.

        Post-conditions:
            - Returns a fully formed response tuple for every documented v1 and v2 route.
            - Unknown routes return 404; malformed flag keys or comparison requests
              return 400 JSON; missing resources return 404.
            - Backward compatible with callers passing only ``(method, path, query, body)``.
        """
        q_params = self._stringify_params(query_params)
        b_params = self._stringify_params(body_params)
        req_headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        verb = (method or "").upper()
        clean_path = path.rstrip("/") or "/"

        static_response = self._serve_static(verb, clean_path)
        if static_response is not None:
            return static_response

        # 1. Main Dashboard HTML Page (SSR) and HEAD variant.
        if verb in ("GET", "HEAD") and clean_path == "/":
            deals, kpis, filters = await self._get_filtered_state(q_params)
            html_body = await self._render_full_page(deals, kpis, filters) if verb == "GET" else ""
            return _html_response(html_body)

        # 2. HTMX Partial: Filtered Deals Grid / Table.
        if verb == "GET" and clean_path == "/partials/deals":
            deals, kpis, filters = await self._get_filtered_state(q_params)
            return _html_response(render_deals_section(deals, kpis, filters))

        # 3. HTMX Partial: KPI telemetry strip.
        if verb == "GET" and clean_path == "/partials/kpis":
            deals, kpis, _filters = await self._get_filtered_state(q_params)
            return _html_response(render_kpis_partial(kpis))

        # 4. HTMX Partial: Listing Price History & Score Breakdown Modal.
        m_hist = re.match(r"^/partials/listing/([^/]+)/history$", clean_path)
        if verb == "GET" and m_hist:
            listing_id = urllib.parse.unquote(m_hist.group(1))
            history_data = await self.repo.get_listing_history(listing_id)
            return _html_response(render_listing_history_modal(history_data))

        # 5. HTMX Partial: NHTSA & EPA Model Intelligence Modal.
        if verb == "GET" and clean_path == "/partials/model-profile":
            make = q_params.get("make", "Mercedes-Benz")
            model = q_params.get("model", "EQS")
            year = _parse_int(q_params.get("year")) or 2023
            profile = await self.repo.get_model_intelligence(make, model, year)
            return _html_response(render_model_profile_modal(profile))

        # 6. HTMX Action: Toggle Bookmark / Star (JSON-aware, v1 HTML contract preserved).
        m_bm = re.match(r"^/api/listing/([^/]+)/bookmark$", clean_path)
        if verb == "POST" and m_bm:
            listing_id = urllib.parse.unquote(m_bm.group(1))
            merged_params = {**q_params, **b_params}
            return await self._toggle_flag_response(listing_id, "user_bookmarked", q_params, req_headers, merged_params)

        # 7. HTMX Action: Toggle Dismiss / Hide (JSON-aware, v1 HTML contract preserved).
        m_dis = re.match(r"^/api/listing/([^/]+)/dismiss$", clean_path)
        if verb == "POST" and m_dis:
            listing_id = urllib.parse.unquote(m_dis.group(1))
            merged_params = {**q_params, **b_params}
            return await self._toggle_flag_response(listing_id, "user_dismissed", q_params, req_headers, merged_params)

        # 8. v2 API: Canonical flag toggle endpoint with key normalization.
        m_flag = re.match(r"^/api/listings/([^/]+)/flag/([^/]+)$", clean_path)
        if verb == "POST" and m_flag:
            listing_id = urllib.parse.unquote(m_flag.group(1))
            raw_key = urllib.parse.unquote(m_flag.group(2)).strip()
            norm_key = _FLAG_KEY_ALIASES.get(raw_key)
            if norm_key is None:
                return _json_response(
                    {
                        "error": f"Invalid flag key: {raw_key}",
                        "allowed": sorted(set(_FLAG_KEY_ALIASES.values())),
                    },
                    status=400,
                )
            merged_params = {**q_params, **b_params}
            return await self._toggle_flag_response(
                listing_id, norm_key, q_params, req_headers, merged_params, force_json=True
            )

        # 9. HTMX Action / v2 API: Trigger Temporal Marketplace Scan.
        if verb == "POST" and clean_path == "/api/scan":
            target_spec = self._resolve_scan_target(b_params, q_params)
            wf_id, err = await self.trigger_scan_workflow(target_spec)
            if wf_id and not err:
                self._last_scan_workflow_id = wf_id

            if _wants_json(q_params, req_headers):
                return _json_response(
                    {
                        "started": bool(wf_id and not err),
                        "workflow_id": wf_id,
                        "error": err,
                        "temporal_available": bool(HAS_TEMPORAL),
                        "temporal_ui_url": settings.temporal_ui_url,
                    }
                )

            if err or not wf_id:
                return _html_response(_scan_error_banner(err))
            banner = render_scan_status_banner(wf_id, {"is_completed": False, "total_scraped": 0, "total_scored": 0})
            return _html_response(banner)

        # 10. v2 API: Latest/selected scan status (falls back to the last started workflow).
        if verb == "GET" and clean_path == "/api/scan/status":
            target_wf_id = q_params.get("workflow_id") or self._last_scan_workflow_id
            if _wants_html(q_params, req_headers):
                if target_wf_id:
                    summary = await self.query_scan_workflow(target_wf_id)
                    return _html_response(render_scan_status_banner(target_wf_id, summary))
                return _html_response('<div class="text-muted text-xs">No active scan workflow.</div>')
            return _json_response(await self._scan_status_payload(target_wf_id))

        # 11. HTMX Poller / v2 API: Query Temporal Scan Progress for a specific workflow.
        m_scan = re.match(r"^/api/scan/([^/]+)/status$", clean_path)
        if verb == "GET" and m_scan:
            wf_id = urllib.parse.unquote(m_scan.group(1))
            if _wants_json(q_params, req_headers):
                return _json_response(await self._scan_status_payload(wf_id))
            summary = await self.query_scan_workflow(wf_id)
            return _html_response(render_scan_status_banner(wf_id, summary))

        # 12. Export CSV.
        if verb == "GET" and clean_path == "/api/export/csv":
            deals, _kpis, _filters = await self._get_filtered_state(q_params)
            csv_text = self.repo.export_deals_csv(deals)
            headers = {
                "Content-Type": "text/csv; charset=utf-8",
                "Content-Disposition": 'attachment; filename="bay_area_ev_deals.csv"',
            }
            return 200, headers, csv_text.encode("utf-8")

        # 13. Export Markdown.
        if verb == "GET" and clean_path == "/api/export/markdown":
            deals, _kpis, _filters = await self._get_filtered_state(q_params)
            md_text = self.repo.export_deals_markdown(deals)
            headers = {
                "Content-Type": "text/markdown; charset=utf-8",
            }
            return 200, headers, md_text.encode("utf-8")

        # 14. v2 JSON REST API: Filtered deal collection with provenance.
        if verb == "GET" and clean_path == "/api/deals":
            deals, kpis, filters = await self._get_filtered_state(q_params)
            return _json_response(
                {
                    "provenance": self.repo.get_provenance(),
                    "kpis": kpis,
                    "filters": filters,
                    "count": len(deals),
                    "deals": deals,
                }
            )

        # 15. Healthcheck endpoint.
        if verb == "GET" and clean_path == "/api/health":
            return _json_response(
                {
                    "status": "ok",
                    "service": "car-researcher-dashboard",
                    "provenance": self.repo.get_provenance(),
                }
            )

        # 16. v2 Market Intelligence: aggregate market overview.
        if verb == "GET" and clean_path == "/api/market/overview":
            overview = await self.repo.get_market_overview()
            return _json_response(overview)

        # 17. v2 Market Intelligence: cohort distributions and scatter points.
        if verb == "GET" and clean_path == "/api/market/cohorts":
            cohorts = await self.repo.get_market_cohorts(
                cohort_key=q_params.get("cohort"),
                make=q_params.get("make"),
                model=q_params.get("model"),
            )
            return _json_response(cohorts)

        # 18. v2 Market Intelligence: dealer, platform, and distance-band arbitrage.
        if verb == "GET" and clean_path == "/api/market/dealers":
            arbitrage = await self.repo.get_dealer_arbitrage()
            return _json_response(arbitrage)

        # 19. v2 API: Listing price history JSON (modal endpoint stays HTML-only).
        m_hist_json = re.match(r"^/api/listings/([^/]+)/history$", clean_path)
        if verb == "GET" and m_hist_json:
            listing_id = urllib.parse.unquote(m_hist_json.group(1))
            history = await self.repo.get_listing_history(listing_id)
            if history is None:
                return _json_response({"error": "Listing not found", "id": listing_id}, status=404)
            return _json_response(
                {
                    "deal": history.get("deal") or history.get("listing"),
                    "snapshots": history.get("snapshots", []),
                    "provenance": self.repo.get_provenance(),
                }
            )

        # 20. v2 API: Full quantitative valuation dossier for a single listing.
        m_analysis = re.match(r"^/api/listings/([^/]+)/analysis$", clean_path)
        if verb == "GET" and m_analysis:
            listing_id = urllib.parse.unquote(m_analysis.group(1))
            analysis = await self.repo.get_listing_analysis(listing_id)
            if analysis is None:
                return _json_response({"error": "Listing not found", "id": listing_id}, status=404)
            return _json_response(analysis)

        # 21. v2 API: Model intelligence dossier (NHTSA recalls/complaints + EPA specs).
        m_model = re.match(r"^/api/models/([^/]+)/([^/]+)/([^/]+)$", clean_path)
        if verb == "GET" and m_model:
            make = urllib.parse.unquote(m_model.group(1))
            model = urllib.parse.unquote(m_model.group(2))
            raw_year = urllib.parse.unquote(m_model.group(3))
            year = _parse_int(raw_year)
            if year is None:
                return _json_response(
                    {"error": "Year must be a valid integer", "year": raw_year},
                    status=400,
                )
            profile = await self.repo.get_model_intelligence(make, model, year)
            return _json_response(profile)

        # 22. v2 API: Side-by-side comparator (maximum 3 listings).
        if verb == "GET" and clean_path == "/api/compare":
            raw_ids = [pid.strip() for pid in (q_params.get("ids", "") or "").split(",")]
            raw_ids = [pid for pid in raw_ids if pid]
            if len(raw_ids) > MAX_COMPARE_IDS:
                return _json_response(
                    {"error": f"Maximum {MAX_COMPARE_IDS} listings can be compared simultaneously", "ids": raw_ids},
                    status=400,
                )
            comparison = await self.repo.get_compare_data(raw_ids)
            return _json_response(comparison)

        return _text_response(404, "Not Found")

    @staticmethod
    def _resolve_scan_target(b_params: Dict[str, str], q_params: Dict[str, str]) -> str:
        """
        Resolve the scan target descriptor from body or query parameters.

        Pre-conditions:
            - b_params and q_params are flattened string maps of body and query values.

        Post-conditions:
            - Returns ``"ALL"`` when no target was supplied, otherwise the trimmed
              ``"Make|Model"`` (or free-form) target string.
        """
        for source in (b_params, q_params):
            raw_target = source.get("target")
            if raw_target:
                return str(raw_target).strip()
        return "ALL"


async def _parse_json_body(body_bytes: bytes) -> Dict[str, Any]:
    """
    Decode an ``application/json`` request body into a parameter dictionary.

    Pre-conditions:
        - body_bytes contains the raw request payload.

    Post-conditions:
        - Returns the decoded mapping for JSON object payloads, or an empty dictionary
          for malformed or non-object JSON documents. Never raises.
    """
    if not body_bytes:
        return {}
    try:
        decoded = json.loads(body_bytes.decode("utf-8", errors="ignore"))
    except (ValueError, TypeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _read_request_headers(header_lines: List[bytes]) -> Dict[str, str]:
    """
    Parse raw HTTP header lines into a lowercased header map.

    Pre-conditions:
        - header_lines is a list of raw header lines (excluding the request line and
          the terminating blank line).

    Post-conditions:
        - Returns a map of lowercased header names to stripped values; malformed lines
          without a colon are ignored.
    """
    req_headers: Dict[str, str] = {}
    for raw_line in header_lines:
        text_line = raw_line.decode("utf-8", errors="ignore").strip()
        if not text_line or ":" not in text_line:
            continue
        name, _, value = text_line.partition(":")
        req_headers[name.strip().lower()] = value.strip()
    return req_headers


def _status_text(status_code: int) -> str:
    """
    Map an HTTP status code to its reason phrase.

    Pre-conditions:
        - status_code is an integer HTTP status code.

    Post-conditions:
        - Returns the canonical reason phrase for 200, 400, 403, 404, and 500, and a
          generic phrase for any other code.
    """
    return _HTTP_STATUS_TEXTS.get(status_code, "OK")


async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, app: DashboardApp) -> None:
    """
    Lightweight async HTTP/1.1 connection handler.

    Pre-conditions:
        - reader and writer are connected asyncio streams for a single client connection.
        - app is the dashboard controller instance.

    Post-conditions:
        - A complete HTTP/1.1 response (status line, headers, body) is written for any
          parsable request, including 500 responses when routing raises.
        - Lowercased request headers and JSON or URL-encoded bodies are forwarded to
          ``app.handle_request``; the socket is always closed.
    """
    try:
        request_line = await asyncio.wait_for(reader.readline(), timeout=10.0)
        if not request_line:
            return
        parts = request_line.decode("utf-8", errors="ignore").strip().split(" ")
        if len(parts) < 2:
            return
        method, raw_target = parts[0].upper(), parts[1]

        header_lines: List[bytes] = []
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not line or line in (b"\r\n", b"\n"):
                break
            header_lines.append(line)

        req_headers = _read_request_headers(header_lines)
        content_length = _parse_int(req_headers.get("content-length")) or 0

        body_bytes = b""
        if content_length > 0:
            body_bytes = await asyncio.wait_for(reader.readexactly(content_length), timeout=5.0)

        parsed_url = urllib.parse.urlsplit(raw_target)
        query_params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed_url.query, keep_blank_values=True).items()}

        content_type = req_headers.get("content-type", "")
        if "application/json" in content_type.lower():
            body_params: Dict[str, Any] = await _parse_json_body(body_bytes)
        elif body_bytes:
            body_str = body_bytes.decode("utf-8", errors="ignore")
            body_params = {k: v[0] for k, v in urllib.parse.parse_qs(body_str, keep_blank_values=True).items()}
        else:
            body_params = {}

        try:
            status_code, resp_headers, resp_body = await app.handle_request(
                method=method,
                path=parsed_url.path,
                query_params=query_params,
                body_params=body_params,
                headers=req_headers,
            )
        except Exception as exc:
            logger.warning(f"Dashboard request routing failure for {method} {parsed_url.path}: {exc}")
            status_code = 500
            resp_headers = {"Content-Type": CONTENT_TYPE_JSON}
            resp_body = json.dumps({"error": "Internal Server Error"}).encode("utf-8")

        header_lines_out = [
            f"HTTP/1.1 {status_code} {_status_text(status_code)}",
            f"Content-Length: {len(resp_body)}",
            "Connection: close",
        ]
        for hk, hv in resp_headers.items():
            header_lines_out.append(f"{hk}: {hv}")

        raw_response = ("\r\n".join(header_lines_out) + "\r\n\r\n").encode("utf-8") + resp_body
        writer.write(raw_response)
        await writer.drain()
    except Exception as e:
        logger.debug(f"Dashboard HTTP connection error: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def start_dashboard_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """
    Initialize DB tables if needed and run the async Web Dashboard server.

    Pre-conditions:
        - host and port are a reachable bind address and free TCP port.

    Post-conditions:
        - Serves the dashboard until cancelled; logs the bind URL without emojis and
          without any hardcoded Temporal UI host.
    """
    try:
        from src.db.engine import init_db
        await init_db()
    except Exception as e:
        logger.warning(f"Dashboard DB init check: {e}")

    app = DashboardApp()
    server = await asyncio.start_server(lambda r, w: _handle_client(r, w, app), host=host, port=port)
    logger.info(f"Car Researcher Web Dashboard live on http://{host}:{port}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    asyncio.run(start_dashboard_server())
