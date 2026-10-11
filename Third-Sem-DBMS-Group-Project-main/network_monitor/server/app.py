from flask import Flask, send_from_directory
from pathlib import Path

from routes.events import events_bp
from routes.dashboard import dashboard_bp
from routes.alerts import alerts_bp

# ============================================================
# APPLICATION
# ============================================================

app = Flask(__name__)


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DASHBOARD_DIR = BASE_DIR / "dashboard"
DASHBOARD_CSS_DIR = DASHBOARD_DIR / "css"
DASHBOARD_JS_DIR = DASHBOARD_DIR / "js"


print("\nDASHBOARD PATH:")
print(DASHBOARD_DIR)
print("Dashboard exists:", DASHBOARD_DIR.exists())
print("HTML exists:", (DASHBOARD_DIR / "dashboard.html").exists())
print()


# ============================================================
# API ROUTES
# ============================================================

app.register_blueprint(
    events_bp,
    url_prefix="/api/v1"
)

app.register_blueprint(
    dashboard_bp,
    url_prefix="/api/v1/dashboard"
)
app.register_blueprint(alerts_bp)


# ============================================================
# DASHBOARD HTML
# ============================================================

@app.get("/dashboard")
def dashboard():

    return send_from_directory(
        DASHBOARD_DIR,
        "dashboard.html"
    )


# ============================================================
# DASHBOARD CSS
# ============================================================

@app.get("/dashboard/css/<path:filename>")
def dashboard_css(filename):

    return send_from_directory(
        DASHBOARD_CSS_DIR,
        filename
    )


# ============================================================
# DASHBOARD JAVASCRIPT
# ============================================================

@app.get("/dashboard/js/<path:filename>")
def dashboard_js(filename):

    return send_from_directory(
        DASHBOARD_JS_DIR,
        filename
    )


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return {
        "status": "online",
        "service": "Network Monitoring API",
        "dashboard": "/dashboard"
    }


# ============================================================
# REGISTERED ROUTES
# ============================================================

print("\nREGISTERED ROUTES:")

for rule in app.url_map.iter_rules():

    print(
        rule,
        "->",
        rule.methods
    )

print()


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )