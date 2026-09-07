from __future__ import annotations


def normalize(app):
    """Remove legacy duplicate routes so hardened canonical handlers win."""
    canonical = {
        '/api/health',
        '/api/status',
        '/api/degraded',
    }
    app.router.routes = [
        route for route in app.router.routes
        if getattr(route, 'path', None) not in canonical
    ]
