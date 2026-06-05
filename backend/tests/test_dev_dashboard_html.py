from fastapi.testclient import TestClient


def _dashboard_html() -> str:
    from api import app

    response = TestClient(app).get("/dev/")
    assert response.status_code == 200
    return response.text


def test_dev_dashboard_uses_app_shell_sidebar_navigation():
    html = _dashboard_html()

    assert 'id="dashboardShell"' in html
    assert 'id="dashboardSidebar"' in html
    assert 'id="activeSectionTitle"' in html
    assert 'id="activeSectionDescription"' in html
    assert "Operations" in html
    assert "Inspection" in html
    assert "Assets" in html
    assert 'data-section="logs"' in html
    assert 'data-section="telemetry"' in html
    assert 'data-section="jobs"' in html
    assert 'data-section="api"' in html
    assert 'data-section="database"' in html
    assert 'data-section="usage"' in html
    assert 'data-section="files"' in html


def test_dev_dashboard_preserves_feature_panel_hooks():
    html = _dashboard_html()

    required_ids = [
        "panel-logs",
        "panel-telemetry",
        "panel-jobs",
        "panel-api",
        "panel-database",
        "panel-usage",
        "panel-files",
        "filterLevel",
        "filterModule",
        "filterSearch",
        "killAllBtn",
        "viewToggleBtn",
        "pauseBtn",
        "logBody",
        "logRawContainer",
        "statsByLevel",
        "fallbackSummaryCards",
        "jobsContainer",
        "apiEndpointList",
        "apiRequestBuilder",
        "apiResponseViewer",
        "dbTableList",
        "sqlInput",
        "usageServiceCards",
        "usageRecentTable",
        "mdSidebar",
        "fileTree",
        "fileViewerContent",
    ]

    for element_id in required_ids:
        assert f'id="{element_id}"' in html


def test_dev_dashboard_defines_local_app_style_classes():
    html = _dashboard_html()

    assert ".app-shell" in html
    assert ".section-nav-item" in html
    assert ".control-input" in html
    assert ".surface-panel" in html
    assert ".metric-card" in html
    assert ".status-badge" in html
