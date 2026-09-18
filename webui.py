"""WebUI server and API for Kavita VFS.

Provides a lightweight, zero-dependency dashboard and JSON API to inspect:
- VFS sync status and mode
- Aggregated volume and chapter totals
- Collision warnings and details
- Live searchable library table
- Manual sync trigger
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional

from vfs_state import state

logger = logging.getLogger("kavita-vfs.webui")

HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Kavita VFS Dashboard</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #38bdf8;
      --primary-hover: #0ea5e9;
      --success: #22c55e;
      --warning: #f59e0b;
      --danger: #ef4444;
      --danger-bg: rgba(239, 68, 68, 0.15);
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 24px;
    }
    .container { max-width: 1280px; margin: 0 auto; }
    header {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--card-border);
    }
    .title-group h1 { font-size: 1.75rem; font-weight: 700; color: var(--text); display: flex; align-items: center; gap: 10px; }
    .title-group p { color: var(--text-muted); font-size: 0.9rem; margin-top: 4px; }
    .actions { display: flex; align-items: center; gap: 12px; }
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 0.8rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .badge-primary { background: rgba(56, 189, 248, 0.2); color: var(--primary); }
    .badge-success { background: rgba(34, 197, 94, 0.2); color: var(--success); }
    .badge-warning { background: rgba(245, 158, 11, 0.2); color: var(--warning); }
    .badge-danger { background: var(--danger-bg); color: var(--danger); }
    button.btn {
      background-color: var(--primary);
      color: #0f172a;
      border: none;
      padding: 8px 18px;
      font-size: 0.9rem;
      font-weight: 600;
      border-radius: 8px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s;
    }
    button.btn:hover { background-color: var(--primary-hover); transform: translateY(-1px); }
    button.btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }

    /* Stats Grid */
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .card {
      background-color: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 20px;
      display: flex;
      flex-direction: column;
    }
    .card-title { font-size: 0.85rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .card-value { font-size: 2.25rem; font-weight: 700; color: var(--text); margin: 8px 0 4px; }
    .card-sub { font-size: 0.8rem; color: var(--text-muted); }

    /* Collisions Alert Box */
    .alert-panel {
      background-color: var(--danger-bg);
      border: 1px solid var(--danger);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
      display: none;
    }
    .alert-panel.active { display: block; }
    .alert-panel h3 { color: var(--danger); font-size: 1.1rem; display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
    .alert-panel p { font-size: 0.9rem; color: var(--text); margin-bottom: 12px; }
    .collision-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; font-family: var(--font-mono); }
    .collision-table th, .collision-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid rgba(239, 68, 68, 0.2); }
    .collision-table th { color: var(--danger); font-weight: 600; }

    /* Distribution Chips */
    .distributions {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 16px 20px;
      margin-bottom: 24px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }
    .dist-label { font-size: 0.85rem; font-weight: 600; color: var(--text-muted); margin-right: 8px; }
    .chip {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 4px 10px;
      font-size: 0.85rem;
    }
    .chip strong { color: var(--primary); }

    /* Table Section */
    .table-section {
      background-color: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      overflow: hidden;
    }
    .table-header {
      padding: 16px 20px;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      border-bottom: 1px solid var(--card-border);
    }
    .table-header h2 { font-size: 1.15rem; font-weight: 600; }
    .search-box input {
      background: #0f172a;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 8px 14px;
      color: var(--text);
      font-size: 0.9rem;
      width: 280px;
      outline: none;
    }
    .search-box input:focus { border-color: var(--primary); }
    .table-wrapper { overflow-x: auto; max-height: 600px; }
    table.data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
      text-align: left;
    }
    table.data-table th, table.data-table td {
      padding: 12px 16px;
      border-bottom: 1px solid var(--card-border);
    }
    table.data-table th {
      background: #182234;
      font-weight: 600;
      color: var(--text-muted);
      position: sticky;
      top: 0;
      z-index: 1;
    }
    table.data-table tr:hover { background-color: rgba(255, 255, 255, 0.02); }
    .mono { font-family: var(--font-mono); font-size: 0.8rem; }
    .path-cell { max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-muted); }
    .empty-state { padding: 48px; text-align: center; color: var(--text-muted); }

    /* Pagination */
    .pagination-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      background: rgba(15, 23, 42, 0.4);
      border-top: 1px solid var(--card-border);
      flex-wrap: wrap;
      gap: 12px;
    }
    .pagination-controls {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .btn-page {
      background: var(--bg-card);
      border: 1px solid var(--card-border);
      color: var(--text);
      padding: 6px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.8rem;
      font-weight: 500;
      transition: all 0.15s ease;
    }
    .btn-page:hover:not(:disabled) {
      background: var(--primary);
      color: #0f172a;
      border-color: var(--primary);
    }
    .btn-page:disabled {
      opacity: 0.35;
      cursor: not-allowed;
    }
    .page-select {
      background: var(--bg-card);
      border: 1px solid var(--card-border);
      color: var(--text);
      padding: 6px 10px;
      border-radius: 6px;
      font-size: 0.8rem;
      outline: none;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>📚 Kavita VFS Dashboard</h1>
        <p>Real-time Virtual Filesystem Monitor & Statistics</p>
      </div>
      <div class="actions">
        <span id="mode-badge" class="badge badge-primary">Symlink</span>
        <span id="sync-status-badge" class="badge badge-success">Idle</span>
        <button id="cleanup-btn" class="btn" style="background-color: #475569; color: #f8fafc;" onclick="triggerCleanup()">🧹 Cleanup VFS</button>
        <button id="sync-btn" class="btn" onclick="triggerSync()">⚡ Sync Now</button>
      </div>
    </header>

    <!-- Cleanup Notification Box -->
    <div id="cleanup-box" class="alert-panel" style="background: rgba(56, 189, 248, 0.15); border-color: var(--primary);">
      <h3 style="color: var(--primary);">🧹 Cleanup Completed</h3>
      <p id="cleanup-msg"></p>
    </div>

    <!-- Collision Warning Box -->
    <div id="collision-box" class="alert-panel">
      <h3>⚠️ File Collision Warning Detected!</h3>
      <p id="collision-msg">The following files mapped to the same target path and were automatically disambiguated:</p>
      <table class="collision-table">
        <thead>
          <tr>
            <th>Target VFS Path</th>
            <th>Existing Book ID</th>
            <th>Colliding Book ID</th>
            <th>Resolved Path</th>
          </tr>
        </thead>
        <tbody id="collision-rows"></tbody>
      </table>
    </div>

    <!-- Stats Grid -->
    <div class="grid">
      <div class="card">
        <span class="card-title">Total Books</span>
        <span id="stat-books" class="card-value">0</span>
        <span id="stat-books-sub" class="card-sub">Files in VFS</span>
      </div>
      <div class="card">
        <span class="card-title">Total Series</span>
        <span id="stat-series" class="card-value">0</span>
        <span id="stat-series-sub" class="card-sub">Unique series folders</span>
      </div>
      <div class="card">
        <span class="card-title">Total Volumes</span>
        <span id="stat-volumes" class="card-value">0</span>
        <span id="stat-volumes-sub" class="card-sub">Sum of volumes & ranges</span>
      </div>
      <div class="card">
        <span class="card-title">Total Chapters</span>
        <span id="stat-chapters" class="card-value">0</span>
        <span id="stat-chapters-sub" class="card-sub">Sum of chapters & ranges</span>
      </div>
      <div class="card">
        <span class="card-title">Collisions</span>
        <span id="stat-collisions" class="card-value">0</span>
        <span id="stat-collisions-sub" class="card-sub">Conflicting paths</span>
      </div>
    </div>

    <!-- Distributions -->
    <div class="distributions">
      <span class="dist-label">Types:</span>
      <div id="type-chips" style="display: flex; gap: 8px; flex-wrap: wrap;"></div>
      <span class="dist-label" style="margin-left: 16px;">Languages:</span>
      <div id="lang-chips" style="display: flex; gap: 8px; flex-wrap: wrap;"></div>
    </div>

    <!-- Books Table -->
    <div class="table-section">
      <div class="table-header">
        <h2>
          Mapped Books in VFS
          <span id="table-count" class="card-sub" style="margin-left: 8px;">Loading...</span>
        </h2>
        <div class="search-box">
          <input type="text" id="search-input" placeholder="Search series, title, ID, path..." oninput="onSearchInput()">
        </div>
      </div>
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width: 70px;">ID</th>
              <th>Series / Title</th>
              <th style="width: 100px;">Vol</th>
              <th style="width: 100px;">Ch</th>
              <th style="width: 90px;">Type</th>
              <th style="width: 80px;">Lang</th>
              <th>Target VFS File</th>
              <th>Source File</th>
            </tr>
          </thead>
          <tbody id="books-rows">
            <tr><td colspan="8" class="empty-state">Loading books...</td></tr>
          </tbody>
        </table>
      </div>
      <div class="pagination-bar">
        <div style="font-size: 0.85rem; color: var(--text-muted); display: flex; align-items: center; gap: 8px;">
          <span>Items per page:</span>
          <select id="page-size-select" class="page-select" onchange="changePageSize()">
            <option value="50" selected>50</option>
            <option value="100">100</option>
            <option value="250">250</option>
            <option value="500">500</option>
          </select>
        </div>
        <div class="pagination-controls">
          <button id="btn-first" class="btn-page" onclick="goToPage(1)">« First</button>
          <button id="btn-prev" class="btn-page" onclick="goToPage(currentPage - 1)">‹ Prev</button>
          <span style="font-size: 0.85rem; padding: 0 8px;">
            Page <strong id="current-page-num">1</strong> of <strong id="total-pages-num">1</strong>
          </span>
          <button id="btn-next" class="btn-page" onclick="goToPage(currentPage + 1)">Next ›</button>
          <button id="btn-last" class="btn-page" onclick="goToPage(totalPages)">Last »</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    let currentPage = 1;
    let pageSize = 50;
    let totalPages = 1;
    let totalItems = 0;
    let searchQuery = '';
    let searchDebounceTimer = null;

    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();

        // Update badges
        document.getElementById('mode-badge').innerText = (data.mode || 'SYMLINK').toUpperCase();
        const syncBadge = document.getElementById('sync-status-badge');
        if (data.sync_in_progress) {
          syncBadge.className = 'badge badge-warning';
          syncBadge.innerText = 'Syncing...';
          document.getElementById('sync-btn').disabled = true;
        } else if (data.last_error) {
          syncBadge.className = 'badge badge-danger';
          syncBadge.innerText = 'Error';
          document.getElementById('sync-btn').disabled = false;
        } else {
          syncBadge.className = 'badge badge-success';
          syncBadge.innerText = 'Idle';
          document.getElementById('sync-btn').disabled = false;
        }

        // Stats
        document.getElementById('stat-books').innerText = (data.total_books || 0).toLocaleString();
        document.getElementById('stat-series').innerText = (data.total_series || 0).toLocaleString();
        document.getElementById('stat-volumes').innerText = (data.total_volumes || 0).toLocaleString();
        document.getElementById('stat-volumes-sub').innerText = `${data.books_with_volume || 0} books with volume`;
        document.getElementById('stat-chapters').innerText = (data.total_chapters || 0).toLocaleString();
        document.getElementById('stat-chapters-sub').innerText = `${data.books_with_chapter || 0} books with chapter`;
        document.getElementById('stat-collisions').innerText = data.collision_count || 0;

        const collCard = document.getElementById('stat-collisions');
        if (data.collision_count > 0) {
          collCard.style.color = 'var(--danger)';
        } else {
          collCard.style.color = 'var(--success)';
        }

        // Collisions panel
        const collBox = document.getElementById('collision-box');
        if (data.collision_count > 0) {
          collBox.classList.add('active');
          const tbody = document.getElementById('collision-rows');
          tbody.innerHTML = (data.collisions || []).map(c => `
            <tr>
              <td>${c.relpath}</td>
              <td>#${c.existing_book_id}</td>
              <td>#${c.colliding_book_id}</td>
              <td style="color: var(--success);">${c.resolved_path}</td>
            </tr>
          `).join('');
        } else {
          collBox.classList.remove('active');
        }

        // Distributions
        const typeChips = document.getElementById('type-chips');
        typeChips.innerHTML = Object.entries(data.type_counts || {}).map(([k, v]) => `
          <div class="chip">${k}: <strong>${v}</strong></div>
        `).join('') || '<span class="card-sub">None</span>';

        const langChips = document.getElementById('lang-chips');
        langChips.innerHTML = Object.entries(data.language_counts || {}).map(([k, v]) => `
          <div class="chip">${k}: <strong>${v}</strong></div>
        `).join('') || '<span class="card-sub">None</span>';

      } catch (err) {
        console.error('Failed to fetch status:', err);
      }
    }

    function onSearchInput() {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        searchQuery = document.getElementById('search-input').value.trim();
        currentPage = 1;
        fetchBooks();
      }, 300);
    }

    function changePageSize() {
      pageSize = parseInt(document.getElementById('page-size-select').value, 10) || 50;
      currentPage = 1;
      fetchBooks();
    }

    function goToPage(page) {
      if (page < 1 || page > totalPages) return;
      currentPage = page;
      fetchBooks();
    }

    async function fetchBooks() {
      const offset = (currentPage - 1) * pageSize;
      try {
        const res = await fetch(`/api/books?q=${encodeURIComponent(searchQuery)}&limit=${pageSize}&offset=${offset}`);
        const data = await res.json();
        totalItems = data.total || 0;
        totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
        if (currentPage > totalPages) {
          currentPage = totalPages;
        }

        const start = totalItems === 0 ? 0 : offset + 1;
        const end = Math.min(offset + pageSize, totalItems);
        document.getElementById('table-count').innerText =
          `(showing ${start}–${end} of ${totalItems.toLocaleString()} books)`;

        document.getElementById('current-page-num').innerText = currentPage;
        document.getElementById('total-pages-num').innerText = totalPages;

        document.getElementById('btn-first').disabled = (currentPage <= 1);
        document.getElementById('btn-prev').disabled = (currentPage <= 1);
        document.getElementById('btn-next').disabled = (currentPage >= totalPages);
        document.getElementById('btn-last').disabled = (currentPage >= totalPages);

        renderRows(data.items || []);
      } catch (err) {
        console.error('Failed to fetch books:', err);
      }
    }

    function renderRows(items) {
      const tbody = document.getElementById('books-rows');
      if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No matching books found.</td></tr>';
        return;
      }

      tbody.innerHTML = items.map(b => {
        const filename = b.vfs_path ? b.vfs_path.split('/').pop() : (b.vfs_relpath ? b.vfs_relpath.split('/').pop() : '-');
        return `
          <tr>
            <td class="mono"><strong>#${b.book_id}</strong></td>
            <td><strong>${b.series || b.title}</strong></td>
            <td>${b.volume || '-'}</td>
            <td>${b.chapter || '-'}</td>
            <td><span class="chip" style="font-size:0.75rem;">${b.type || '-'}</span></td>
            <td><span class="chip" style="font-size:0.75rem;">${b.language || '-'}</span></td>
            <td class="mono path-cell" title="${b.vfs_path || b.vfs_relpath}">${filename}</td>
            <td class="mono path-cell" title="${b.source_path}">${b.source_path}</td>
          </tr>
        `;
      }).join('');
    }

    async function triggerSync() {
      const btn = document.getElementById('sync-btn');
      btn.disabled = true;
      btn.innerText = '⏳ Triggering...';
      try {
        await fetch('/api/sync', { method: 'POST' });
        setTimeout(() => {
          fetchStatus();
          fetchBooks();
        }, 800);
      } catch (err) {
        alert('Failed to trigger sync: ' + err);
      } finally {
        btn.disabled = false;
        btn.innerText = '⚡ Sync Now';
      }
    }

    async function triggerCleanup() {
      if (!confirm("This will scan the VFS folder, remove any unregistered files or broken links, prune empty directories, and ensure all files match current mode (symlink/hardlink). Proceed?")) {
        return;
      }
      const btn = document.getElementById('cleanup-btn');
      btn.disabled = true;
      btn.innerText = '⏳ Cleaning...';
      try {
        const res = await fetch('/api/cleanup', { method: 'POST' });
        const data = await res.json();
        const box = document.getElementById('cleanup-box');
        box.style.display = 'block';
        document.getElementById('cleanup-msg').innerText = `Cleaned ${data.removed_count} unregistered file(s)/link(s) and pruned ${data.empty_dirs_removed} empty folder(s). Mode sync: ${data.sync_created} created, ${data.sync_updated} updated.`;
        setTimeout(() => { box.style.display = 'none'; }, 8000);
        fetchStatus();
        fetchBooks();
      } catch (err) {
        alert('Cleanup failed: ' + err);
      } finally {
        btn.disabled = false;
        btn.innerText = '🧹 Cleanup VFS';
      }
    }

    // Polling
    fetchStatus();
    fetchBooks();
    setInterval(fetchStatus, 3000);
  </script>
</body>
</html>
"""


class WebUIHandler(BaseHTTPRequestHandler):
    trigger_sync_callback: Optional[Callable[[], None]] = None
    trigger_cleanup_callback: Optional[Callable[[], Dict[str, Any]]] = None

    def log_message(self, format, *args):
        # Silence standard HTTP access logging to prevent cluttering application logs
        pass

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))

        elif path == "/api/status":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = state.get_summary()
            self.wfile.write(json.dumps(data).encode("utf-8"))

        elif path == "/api/books":
            params = urllib.parse.parse_qs(parsed.query)
            q = params.get("q", [""])[0]
            limit = int(params.get("limit", [50])[0])
            offset = int(params.get("offset", [0])[0])

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = state.get_items(query=q, limit=limit, offset=offset)
            self.wfile.write(json.dumps(data).encode("utf-8"))

        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/sync":
            if WebUIHandler.trigger_sync_callback:
                try:
                    WebUIHandler.trigger_sync_callback()
                except Exception as e:
                    logger.exception("Error in manual sync callback: %s", e)

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "sync_triggered"}).encode("utf-8"))

        elif parsed.path == "/api/cleanup":
            result: Dict[str, Any] = {"status": "cleanup_completed", "removed_count": 0, "empty_dirs_removed": 0}
            if WebUIHandler.trigger_cleanup_callback:
                try:
                    result = WebUIHandler.trigger_cleanup_callback()
                except Exception as e:
                    logger.exception("Error in cleanup callback: %s", e)
                    result["error"] = str(e)

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))

        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()


def start_webui_server(
    port: int = 8080,
    trigger_sync_callback: Optional[Callable[[], None]] = None,
    trigger_cleanup_callback: Optional[Callable[[], Dict[str, Any]]] = None,
) -> ThreadingHTTPServer:
    """Start the WebUI HTTP server in a daemon thread."""
    WebUIHandler.trigger_sync_callback = staticmethod(trigger_sync_callback) if trigger_sync_callback else None
    WebUIHandler.trigger_cleanup_callback = staticmethod(trigger_cleanup_callback) if trigger_cleanup_callback else None
    server = ThreadingHTTPServer(("0.0.0.0", port), WebUIHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    logger.info("WebUI server running on http://0.0.0.0:%d", port)
    return server
