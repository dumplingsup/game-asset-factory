"""Small versioned contracts shared by CLI and plugins."""
from jsonschema import Draft202012Validator

LICENSE = {
    "type": "object", "required": ["schema_version", "title", "author", "source_url", "source_version", "license", "evidence", "rights"],
    "properties": {
        "schema_version": {"const": 1},
        **{k: {"type": "string", "minLength": 1} for k in ["title", "author", "source_url", "source_version", "license"]},
        "evidence": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "rights": {"type": "object", "required": ["commercial_use", "modification", "runtime_distribution", "source_distribution", "third_party_upload"], "additionalProperties": False,
                   "properties": {k: {"type": "boolean"} for k in ["commercial_use", "modification", "runtime_distribution", "source_distribution", "third_party_upload"]}},
        "expected_source_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    }
}
BLENDER_RECIPE = {
    "type": "object", "additionalProperties": False,
    "required": ["schema_version", "build_plugin", "blender_version", "objects", "height_m", "subdivision_level"],
    "properties": {
        "schema_version": {"const": 1}, "build_plugin": {"const": "blender-static"},
        "blender_version": {"type": "string", "pattern": "^[0-9]+[.][0-9]+[.][0-9]+$"},
        "objects": {"type": "array", "items": {"type": "string", "minLength": 1}, "uniqueItems": True},
        "height_m": {"type": "number", "exclusiveMinimum": 0, "maximum": 1000},
        "subdivision_level": {"type": "integer", "minimum": 0, "maximum": 2},
        "rotation_z_degrees": {"type": "number", "minimum": -360, "maximum": 360},
    }
}

RECIPE = {
    "type": "object", "required": ["schema_version", "build_plugin"],
    "properties": {"schema_version": {"const": 1}, "build_plugin": {"type": "string", "pattern": "^[a-z0-9][a-z0-9_-]{0,79}$"}},
    "allOf": [{"if": {"properties": {"build_plugin": {"const": "blender-static"}}}, "then": BLENDER_RECIPE}],
}

CHARACTER_RECIPE = {
    "type": "object", "additionalProperties": False,
    "required": ["schema_version", "build_plugin", "blender_version", "height_m", "rotation_z_degrees", "animation_fps"],
    "properties": {"schema_version": {"const": 1}, "build_plugin": {"const": "blender-character"},
                   "blender_version": {"type": "string", "pattern": "^[0-9]+[.][0-9]+[.][0-9]+$"},
                   "height_m": {"type": ["number", "null"], "exclusiveMinimum": 0},
                   "rotation_z_degrees": {"type": "number", "minimum": -360, "maximum": 360},
                   "animation_fps": {"type": "integer", "minimum": 24, "maximum": 120},
                   "static_pose_actions": {"type": "array", "items": {"type": "string", "minLength": 1}, "uniqueItems": True},
                   "morph_targets": {"enum": ["reject", "preserve"]}},
}
RECIPE['allOf'].append({"if": {"properties": {"build_plugin": {"const": "blender-character"}}}, "then": CHARACTER_RECIPE})

CHARACTER_PREVIEW = {
    "type":"object", "required":["schema_version"], "additionalProperties":False,
    "properties": {
        "schema_version":{"const":1},
        "mode":{"enum":["inspection","third_person","performance","interactive"]},
        **{k:{"type":"string","minLength":1} for k in ("idle_clip","walk_clip","attack_clip")},
        "capture_views":{"type":"boolean"}, "capture_morphs":{"type":"boolean"},
        "face_center_offset":{"type":"array","minItems":3,"maxItems":3,"items":{"type":"number"}},
        "face_size_m":{"type":"number","minimum":0.1,"maximum":5},
        "walk_speed_mps":{"type":"number","minimum":0.1,"maximum":10},
        "equipment_sets":{"type":"array","items":{"type":"object","required":["name","active"],"additionalProperties":False,
            "properties":{"name":{"type":"string","minLength":1},"active":{"type":"array","items":{"type":"string","minLength":1},"uniqueItems":True}}}},
        "warmup_frames":{"type":"integer","minimum":30,"maximum":1000},
        "sample_frames":{"type":"integer","minimum":60,"maximum":5000},
        "p95_frame_budget_ms":{"type":"number","exclusiveMinimum":0,"maximum":1000}
    }
}


def check(data, schema):
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: str(e.path))
    if errors:
        raise ValueError("; ".join(f"{'.'.join(map(str, e.path))}: {e.message}" for e in errors))
