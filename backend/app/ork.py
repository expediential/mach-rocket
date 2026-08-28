"""Tolerant, non-mutating OpenRocket XML artifact extractor.

OpenRocket's saved XML has evolved, so this parser only normalizes fields that
are explicitly present.  Unknown component XML remains in the retained source
artifact rather than being guessed at.
"""
from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from typing import Any


COMPONENT_TYPES = {
    "bodytube": "RocketBody",
    "nosecone": "NoseCone",
    "trapezoidfinset": "FinSet",
    "ellipticalfinset": "FinSet",
    "freeformfinset": "FinSet",
    "masscomponent": "PayloadSection",
    "payload": "PayloadSection",
    "innertube": "MotorSection",
    "engineblock": "MotorSection",
    "transition": "PayloadSection",
}


def _tag(node: ElementTree.Element) -> str:
    return node.tag.rsplit("}", 1)[-1].lower()


def _text(node: ElementTree.Element, names: set[str]) -> str | None:
    for child in node.iter():
        if _tag(child) in names and (child.text or "").strip():
            return (child.text or "").strip()
    return None


def _number(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _component(node: ElementTree.Element, ordinal: int) -> dict[str, Any] | None:
    xml_type = _tag(node)
    component_type = COMPONENT_TYPES.get(xml_type)
    if not component_type:
        return None
    length = _number(_text(node, {"length", "forelength"}))
    radius = _number(_text(node, {"radius", "outerradius", "aftradius"}))
    diameter = _number(_text(node, {"diameter", "outerdiameter"}))
    position = _number(_text(node, {"axialposition", "position"}))
    component: dict[str, Any] = {
        "id": f"ork-{ordinal}-{xml_type}",
        "type": component_type,
        "label": _text(node, {"name"}) or xml_type.replace("finset", " fin set").replace("tube", " tube").title(),
        "source": "OpenRocket-derived",
    }
    if length is not None:
        component["length_m"] = length
    if radius is not None:
        component["radius_m"] = radius
    elif diameter is not None:
        component["radius_m"] = diameter / 2
    if position is not None:
        component["position_m"] = position
    mass = _number(_text(node, {"mass", "componentmass"}))
    if mass is not None:
        component["mass_kg"] = mass
    if component_type == "FinSet":
        for field, tags in {"root_m": {"rootchord"}, "tip_m": {"tipchord"}, "span_m": {"height", "span"}}.items():
            value = _number(_text(node, tags))
            if value is not None:
                component[field] = value
        count = _number(_text(node, {"fincount"}))
        if count is not None:
            component["count"] = int(count)
    return component


def parse_ork(content: str) -> dict[str, Any]:
    """Extract recognizable dimensions, component hierarchy, and metadata safely."""
    result: dict[str, Any] = {"rocket_name": None, "stages": 0, "mass_kg": None, "length_m": None, "motor": None, "components": [], "warnings": []}
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        result["warnings"].append(f"Could not parse OpenRocket XML: {exc}")
        return result
    ordinal = 0
    for node in root.iter():
        tag = _tag(node)
        text = (node.text or "").strip()
        if tag == "rocket" and node.get("name"):
            result["rocket_name"] = node.get("name")
        elif tag == "name" and not result["rocket_name"] and text:
            result["rocket_name"] = text
        elif tag in {"stage", "axialstage"}:
            result["stages"] += 1
        elif tag in {"mass", "launchmass"} and text and result["mass_kg"] is None:
            result["mass_kg"] = _number(text)
        elif tag in {"length", "forelength"} and text and result["length_m"] is None:
            result["length_m"] = _number(text)
        elif "motor" in tag and text and result["motor"] is None:
            result["motor"] = text
        component = _component(node, ordinal)
        if component:
            ordinal += 1
            result["components"].append(component)
    if not result["rocket_name"]:
        result["warnings"].append("Rocket name was not present in this artifact.")
    if not result["components"]:
        result["warnings"].append("No supported component geometry was present; a 2D/3D model was not reconstructed.")
    return result
