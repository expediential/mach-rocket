"""Tolerant, non-mutating OpenRocket XML artifact extractor."""
from __future__ import annotations

import xml.etree.ElementTree as ElementTree


def parse_ork(content: str) -> dict:
    """Extract optional recognizable fields and retain warnings instead of failing."""
    result = {"rocket_name": None, "stages": 0, "mass_kg": None, "length_m": None, "motor": None, "warnings": []}
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        result["warnings"].append(f"Could not parse OpenRocket XML: {exc}")
        return result
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1].lower()
        text = (node.text or "").strip()
        if tag == "rocket" and node.get("name"):
            result["rocket_name"] = node.get("name")
        elif tag == "name" and not result["rocket_name"] and text:
            result["rocket_name"] = text
        elif tag in {"stage", "axialstage"}:
            result["stages"] += 1
        elif tag in {"mass", "launchmass"} and text and result["mass_kg"] is None:
            result["mass_kg"] = text
        elif tag in {"length", "forelength"} and text and result["length_m"] is None:
            result["length_m"] = text
        elif "motor" in tag and text and result["motor"] is None:
            result["motor"] = text
    if not result["rocket_name"]:
        result["warnings"].append("Rocket name was not present in this artifact.")
    return result
