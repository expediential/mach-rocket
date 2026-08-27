"""Human-readable HTML report generator for local download."""
from __future__ import annotations

from html import escape


def build_report(dashboard: dict, comparison: dict, tests: dict) -> str:
    """Build a standalone report from stored/derived validation evidence."""
    metrics = [metric.model_dump() if hasattr(metric, "model_dump") else metric for metric in comparison["metrics"]]
    rows = "".join(f"<tr><td>{escape(metric['metric'])}</td><td>{metric['simulation']} {metric['unit']}</td><td>{metric['actual']} {metric['unit']}</td><td>{metric['difference']} {metric['unit']}</td><td>{escape(metric['classification'])}</td></tr>" for metric in metrics)
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Mission Validation Report</title><style>body{{font:15px system-ui;margin:42px;color:#102238}}h1{{color:#0b5d72}}table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;border-bottom:1px solid #d8e0e8;text-align:left}}.fail{{color:#a22;font-weight:700}}</style></head><body><h1>Mission Validation Report</h1><p><strong>{escape(dashboard['project']['name'])}</strong> — {escape(dashboard['mission']['name'])}</p><h2>Scope and limitation</h2><p>This is a software-verification simulation and decision-support report. It is not a flight-safety certification and does not replace physical testing or professional flight-dynamics analysis.</p><h2>Mission health</h2><p>{dashboard['health']['score']} / 100 — {escape(dashboard['health']['summary'])}</p><h2>Test summary</h2><p>{tests['passed']} passed, {tests['warnings']} warnings, <span class='fail'>{tests['failed']} failed</span>. {escape(tests['headline'])}</p><h2>Simulation versus actual flight</h2><table><tr><th>Metric</th><th>Simulation</th><th>Actual</th><th>Difference</th><th>Classification</th></tr>{rows}</table><h2>Potential areas to investigate</h2><ul>{''.join(f'<li>{escape(item)}</li>' for item in comparison['investigation_areas'])}</ul></body></html>"""
