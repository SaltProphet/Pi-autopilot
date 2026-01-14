#!/usr/bin/env python3
"""
Real-time dashboard for Pi-Autopilot pipeline monitoring.
Serves a live web UI with status, costs, and recent activity.

Run with: python dashboard.py
Access at: http://localhost:8000
"""

from fastapi import FastAPI, WebSocket, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import sqlite3
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
import asyncio
import os
import secrets

from config import settings
from services.config_manager import ConfigManager

app = FastAPI()

# HTTP Basic Auth for dashboard
security = HTTPBasic()

# Initialize ConfigManager
config_manager = ConfigManager()

# Security middleware for IP whitelisting
class IPWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip whitelisting for config endpoints if no restriction set
        allowed_ips_str = os.getenv('DASHBOARD_ALLOWED_IPS', '')
        
        if not allowed_ips_str:
            # No IP restriction
            return await call_next(request)
        
        allowed_ips = [ip.strip() for ip in allowed_ips_str.split(',')]
        client_ip = request.client.host
        
        # Allow if client IP is in whitelist
        if client_ip in allowed_ips or '0.0.0.0' in allowed_ips:
            return await call_next(request)
        
        return JSONResponse(
            status_code=403,
            content={"error": "Access denied: IP not whitelisted"}
        )

# Add IP whitelist middleware
app.add_middleware(IPWhitelistMiddleware)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), 'static')
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


def verify_dashboard_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify dashboard authentication if password is set.
    
    Args:
        credentials: HTTP Basic Auth credentials
    
    Returns:
        True if authenticated
    
    Raises:
        HTTPException: If authentication fails
    """
    dashboard_password = os.getenv('DASHBOARD_PASSWORD', '')
    
    # No password set - allow access
    if not dashboard_password:
        return True
    
    # Verify password
    if not secrets.compare_digest(credentials.password, dashboard_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"}
        )
    
    return True

@contextmanager
def get_db():
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_pipeline_stats(hours: int = 24):
    """Get pipeline stats for the last N hours."""
    with get_db() as conn:
        # Cost stats
        cutoff_time = datetime.now() - timedelta(hours=hours)
        cutoff_timestamp = cutoff_time.isoformat()
        
        cost_result = conn.execute("""
            SELECT 
                SUM(usd_cost) as total_cost,
                SUM(tokens_sent) as total_input_tokens,
                SUM(tokens_received) as total_output_tokens,
                COUNT(*) as total_calls
            FROM cost_tracking
            WHERE timestamp > ?
        """, (cutoff_timestamp,)).fetchone()
        
        # Pipeline stats
        pipeline_result = conn.execute("""
            SELECT 
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'discarded' THEN 1 END) as discarded,
                COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
            FROM pipeline_runs
            WHERE created_at > strftime('%s', ?)
        """, (cutoff_time.isoformat(),)).fetchone()
        
        # Lifetime cost
        lifetime_result = conn.execute("""
            SELECT SUM(usd_cost) as lifetime_cost FROM cost_tracking
        """).fetchone()
        
        return {
            "period_hours": hours,
            "cost": {
                "last_period": round(cost_result["total_cost"] or 0, 4),
                "lifetime": round(lifetime_result["lifetime_cost"] or 0, 2),
                "max_per_run": settings.max_usd_per_run,
                "max_lifetime": settings.max_usd_lifetime,
                "lifetime_remaining": round((settings.max_usd_lifetime - (lifetime_result["lifetime_cost"] or 0)), 2)
            },
            "tokens": {
                "sent": cost_result["total_input_tokens"] or 0,
                "received": cost_result["total_output_tokens"] or 0
            },
            "pipeline": {
                "completed": pipeline_result["completed"],
                "discarded": pipeline_result["discarded"],
                "rejected": pipeline_result["rejected"],
                "failed": pipeline_result["failed"]
            }
        }


def get_recent_activity(limit: int = 20):
    """Get recent pipeline activity."""
    with get_db() as conn:
        activities = conn.execute("""
            SELECT 
                timestamp,
                action,
                post_id,
                details,
                error_occurred
            FROM audit_log
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,)).fetchall()
        
        return [
            {
                "timestamp": row["timestamp"],
                "action": row["action"],
                "post_id": row["post_id"],
                "details": json.loads(row["details"]) if row["details"] else {},
                "error": bool(row["error_occurred"])
            }
            for row in activities
        ]


def get_active_posts():
    """Get posts currently being processed."""
    with get_db() as conn:
        posts = conn.execute("""
            SELECT 
                p.id,
                p.title,
                p.score,
                p.subreddit,
                MAX(pr.created_at) as last_activity,
                pr.stage,
                pr.status
            FROM reddit_posts p
            LEFT JOIN pipeline_runs pr ON p.id = pr.post_id
            GROUP BY p.id
            HAVING pr.status != 'completed' AND pr.status != 'discarded' AND pr.status != 'rejected'
            ORDER BY pr.created_at DESC
            LIMIT 10
        """).fetchall()
        
        return [
            {
                "id": row["id"],
                "title": row["title"][:80],
                "score": row["score"],
                "subreddit": row["subreddit"],
                "stage": row["stage"],
                "status": row["status"],
                "last_activity": row["last_activity"]
            }
            for row in posts
        ]


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the dashboard HTML."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Pi-Autopilot Dashboard</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            .header {
                color: white;
                margin-bottom: 30px;
            }
            .header h1 {
                font-size: 2.5em;
                margin-bottom: 5px;
            }
            .header p {
                opacity: 0.9;
                font-size: 1.1em;
            }
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .card {
                background: white;
                border-radius: 12px;
                padding: 25px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                transition: transform 0.2s, box-shadow 0.2s;
            }
            .card:hover {
                transform: translateY(-5px);
                box-shadow: 0 15px 40px rgba(0,0,0,0.3);
            }
            .card-title {
                font-size: 0.9em;
                color: #666;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 15px;
                font-weight: 600;
            }
            .card-value {
                font-size: 2.5em;
                font-weight: bold;
                color: #333;
                margin-bottom: 10px;
            }
            .card-sub {
                font-size: 0.9em;
                color: #999;
            }
            .status-badge {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.85em;
                font-weight: 600;
                margin-top: 10px;
            }
            .status-warning { background: #fff3cd; color: #856404; }
            .status-success { background: #d4edda; color: #155724; }
            .status-danger { background: #f8d7da; color: #721c24; }
            
            .wide-card {
                grid-column: 1 / -1;
            }
            
            .activity-list {
                max-height: 400px;
                overflow-y: auto;
            }
            .activity-item {
                padding: 15px;
                border-bottom: 1px solid #eee;
                font-size: 0.95em;
            }
            .activity-item:last-child {
                border-bottom: none;
            }
            .activity-time {
                color: #999;
                font-size: 0.85em;
            }
            .activity-action {
                font-weight: 600;
                color: #667eea;
            }
            .activity-error {
                color: #e74c3c;
            }
            
            .posts-table {
                width: 100%;
                border-collapse: collapse;
            }
            .posts-table th {
                text-align: left;
                padding: 12px;
                border-bottom: 2px solid #ddd;
                background: #f8f9fa;
                font-weight: 600;
                color: #333;
            }
            .posts-table td {
                padding: 12px;
                border-bottom: 1px solid #eee;
            }
            .post-title {
                max-width: 300px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .stage-badge {
                display: inline-block;
                padding: 4px 8px;
                background: #667eea;
                color: white;
                border-radius: 4px;
                font-size: 0.8em;
                font-weight: 600;
            }
            
            .loading {
                text-align: center;
                padding: 40px;
                color: #666;
            }
            .spinner {
                display: inline-block;
                width: 30px;
                height: 30px;
                border: 3px solid #ddd;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            
            .cost-bar {
                background: #f0f0f0;
                border-radius: 8px;
                height: 20px;
                margin: 10px 0;
                overflow: hidden;
            }
            .cost-bar-fill {
                height: 100%;
                background: linear-gradient(90deg, #667eea, #764ba2);
                transition: width 0.3s;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 Pi-Autopilot Dashboard</h1>
                <p>Real-time pipeline monitoring</p>
            </div>
            
            <div id="content">
                <div class="loading">
                    <div class="spinner"></div>
                    <p style="margin-top: 15px;">Loading dashboard...</p>
                </div>
            </div>
        </div>
        
        <script>
            const API_BASE = '/api';
            const REFRESH_INTERVAL = 3000; // 3 seconds
            
            async function fetchStats() {
                try {
                    const response = await fetch(API_BASE + '/stats');
                    return await response.json();
                } catch (e) {
                    console.error('Error fetching stats:', e);
                    return null;
                }
            }
            
            async function fetchActivity() {
                try {
                    const response = await fetch(API_BASE + '/activity');
                    return await response.json();
                } catch (e) {
                    console.error('Error fetching activity:', e);
                    return [];
                }
            }
            
            async function fetchPosts() {
                try {
                    const response = await fetch(API_BASE + '/posts');
                    return await response.json();
                } catch (e) {
                    console.error('Error fetching posts:', e);
                    return [];
                }
            }
            
            function formatTime(isoString) {
                try {
                    const date = new Date(isoString);
                    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                } catch {
                    return isoString;
                }
            }
            
            function renderDashboard(stats, activity, posts) {
                const lifePercent = (stats.cost.lifetime / stats.cost.max_lifetime) * 100;
                const costWarning = lifePercent > 80 ? 'status-danger' : lifePercent > 50 ? 'status-warning' : 'status-success';
                
                const html = `
                    <div class="grid">
                        <div class="card">
                            <div class="card-title">💰 Lifetime Cost</div>
                            <div class="card-value">\\$${stats.cost.lifetime.toFixed(2)}</div>
                            <div class="card-sub">of \\$${stats.cost.max_lifetime.toFixed(2)}</div>
                            <div class="cost-bar">
                                <div class="cost-bar-fill" style="width: ${Math.min(lifePercent, 100)}%"></div>
                            </div>
                            <span class="status-badge ${costWarning}">
                                ${lifePercent.toFixed(0)}% used
                            </span>
                        </div>
                        
                        <div class="card">
                            <div class="card-title">📊 Last 24h Cost</div>
                            <div class="card-value">\\$${stats.cost.last_period.toFixed(4)}</div>
                            <div class="card-sub">Max per run: \\$${stats.cost.max_per_run}</div>
                            <span class="status-badge status-success">Normal</span>
                        </div>
                        
                        <div class="card">
                            <div class="card-title">✅ Completed</div>
                            <div class="card-value">${stats.pipeline.completed}</div>
                            <div class="card-sub">Last 24 hours</div>
                        </div>
                        
                        <div class="card">
                            <div class="card-title">⏭️ Discarded</div>
                            <div class="card-value">${stats.pipeline.discarded}</div>
                            <div class="card-sub">Not monetizable</div>
                        </div>
                        
                        <div class="card">
                            <div class="card-title">❌ Rejected</div>
                            <div class="card-value">${stats.pipeline.rejected}</div>
                            <div class="card-sub">Failed quality gates</div>
                        </div>
                        
                        <div class="card">
                            <div class="card-title">⚠️ Failed</div>
                            <div class="card-value">${stats.pipeline.failed}</div>
                            <div class="card-sub">Errors</div>
                        </div>
                        
                        <div class="card wide-card">
                            <div class="card-title">📍 Active Posts</div>
                            ${posts.length > 0 ? `
                                <table class="posts-table">
                                    <thead>
                                        <tr>
                                            <th>Title</th>
                                            <th>Score</th>
                                            <th>Stage</th>
                                            <th>Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${posts.map(p => `
                                            <tr>
                                                <td class="post-title">${p.title}</td>
                                                <td>${p.score}</td>
                                                <td><span class="stage-badge">${p.stage}</span></td>
                                                <td>${p.status}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            ` : '<p style="color: #999;">No active posts</p>'}
                        </div>
                        
                        <div class="card wide-card">
                            <div class="card-title">📋 Recent Activity</div>
                            <div class="activity-list">
                                ${activity.length > 0 ? activity.map(a => `
                                    <div class="activity-item ${a.error ? 'activity-error' : ''}">
                                        <div class="activity-action">${a.action}</div>
                                        <div class="activity-time">${formatTime(a.timestamp)}</div>
                                        ${a.post_id ? `<div style="color: #666;">Post: ${a.post_id}</div>` : ''}
                                    </div>
                                `).join('') : '<div class="activity-item" style="color: #999;">No recent activity</div>'}
                            </div>
                        </div>
                    </div>
                `;
                
                document.getElementById('content').innerHTML = html;
            }
            
            async function updateDashboard() {
                const [stats, activity, posts] = await Promise.all([
                    fetchStats(),
                    fetchActivity(),
                    fetchPosts()
                ]);
                
                if (stats && activity !== null && posts !== null) {
                    renderDashboard(stats, activity, posts);
                } else {
                    document.getElementById('content').innerHTML = `
                        <div class="card" style="color: red; text-align: center; padding: 40px;">
                            ⚠️ Failed to load dashboard data. Is the database accessible?
                        </div>
                    `;
                }
            }
            
            // Initial load
            updateDashboard();
            
            // Auto-refresh every 3 seconds
            setInterval(updateDashboard, REFRESH_INTERVAL);
        </script>
    </body>
    </html>
    """


@app.get("/api/stats")
async def get_stats():
    """Get pipeline statistics."""
    return get_pipeline_stats(hours=24)


@app.get("/api/activity")
async def get_activity():
    """Get recent activity."""
    return get_recent_activity(limit=20)


@app.get("/api/posts")
async def get_posts():
    """Get active posts."""
    return get_active_posts()


@app.get("/config", response_class=HTMLResponse)
async def get_config_page():
    """Serve the configuration page."""
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    config_html_path = os.path.join(templates_dir, 'config.html')
    
    if os.path.exists(config_html_path):
        with open(config_html_path, 'r') as f:
            return f.read()
    else:
        return """
        <html>
            <body style="font-family: sans-serif; padding: 40px; text-align: center;">
                <h1>Configuration Page Not Found</h1>
                <p>The configuration template has not been created yet.</p>
                <a href="/">← Back to Dashboard</a>
            </body>
        </html>
        """


@app.get("/api/config")
async def get_config(authenticated: bool = Depends(verify_dashboard_auth)):
    """Get current configuration with masked sensitive values.
    
    Returns:
        JSON with configuration organized by category
    """
    try:
        config = config_manager.get_current_config()
        return {"success": True, "config": config}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/config/update")
async def update_config(request: Request, authenticated: bool = Depends(verify_dashboard_auth)):
    """Update configuration with validation.
    
    Request body format:
    {
        "api_keys": {"OPENAI_API_KEY": "sk-...", ...},
        "toggles": {"OPENAI_ENABLED": true, ...},
        "cost_limits": {"MAX_USD_PER_RUN": 5.0, ...},
        "pipeline": {"REDDIT_SUBREDDITS": "Entrepreneur,SaaS", ...}
    }
    
    Returns:
        JSON with success status and any errors
    """
    try:
        updates = await request.json()
        client_ip = request.client.host
        
        success, messages = config_manager.update_config(updates, user_ip=client_ip)
        
        if success:
            return {"success": True, "messages": messages}
        else:
            return {"success": False, "errors": messages}
            
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


@app.post("/api/config/test")
async def test_api_key(request: Request, authenticated: bool = Depends(verify_dashboard_auth)):
    """Test API key validity before saving.
    
    Query parameters:
        service: Service name (OPENAI, REDDIT, GUMROAD)
        api_key: API key to test
    
    Returns:
        JSON with validation result and message
    """
    try:
        params = dict(request.query_params)
        service = params.get('service')
        api_key = params.get('api_key')
        
        if not service or not api_key:
            return {"success": False, "message": "Missing service or api_key parameter"}
        
        is_valid, message = config_manager.test_api_key(service, api_key)
        
        return {"success": is_valid, "message": message}
        
    except Exception as e:
        return {"success": False, "message": f"Test error: {str(e)}"}


@app.get("/api/config/backups")
async def list_config_backups(authenticated: bool = Depends(verify_dashboard_auth)):
    """List all available configuration backups.
    
    Returns:
        JSON list of backup metadata
    """
    try:
        backups = config_manager.list_backups()
        return {"success": True, "backups": backups}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/config/restore")
async def restore_config_backup(request: Request, authenticated: bool = Depends(verify_dashboard_auth)):
    """Restore configuration from a backup file.
    
    Request body:
    {
        "backup_filename": "env_backup_20260114_123456.txt"
    }
    
    Returns:
        JSON with success status and message
    """
    try:
        data = await request.json()
        backup_filename = data.get('backup_filename')
        client_ip = request.client.host
        
        if not backup_filename:
            return {"success": False, "message": "Missing backup_filename"}
        
        success, message = config_manager.restore_backup(backup_filename, user_ip=client_ip)
        
        return {"success": success, "message": message}
        
    except Exception as e:
        return {"success": False, "message": f"Restore error: {str(e)}"}


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Pi-Autopilot Dashboard on http://0.0.0.0:8000")
    print("   Access dashboard at: http://localhost:8000")
    print("   Configuration at: http://localhost:8000/config")
    uvicorn.run(app, host="0.0.0.0", port=8000)
