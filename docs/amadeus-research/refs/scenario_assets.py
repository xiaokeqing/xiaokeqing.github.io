<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   wallpaper/scene_assets.py
     quoted: L62-L67, L83-L102, L277-L293, L393-L464
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- _SCENARIO_DEFAULT_SOURCE_CROP_NORM (crop the baked CRT bezel off scenario art)  [wallpaper/scene_assets.py L62-L67] ---- */
_SCENARIO_DEFAULT_SOURCE_CROP_NORM = [
    113 / 1398,
    119 / 1125,
    1182 / 1398,
    902 / 1125,
]

/* ---- _crt_bounds_norm: authored CRT polygon -> normalized box  [wallpaper/scene_assets.py L83-L102] ---- */
def _crt_bounds_norm(config: dict | None = None) -> dict[str, float]:
    """Project the authored CRT polygon to a host-independent normalized box."""
    value = config if isinstance(config, dict) else _load_crt_config()
    image_size = value.get("img_size") or [1672, 941]
    source_width = max(1.0, float(image_size[0] or 1672))
    source_height = max(1.0, float(image_size[1] or 941))
    points = value.get("crt_polygon") or value.get("crt_corners") or []
    valid = [point for point in points if isinstance(point, (list, tuple)) and len(point) >= 2]
    if len(valid) < 3:
        valid = [[556, 199], [1132, 199], [1132, 630], [556, 630]]
    xs = [float(point[0]) / source_width for point in valid]
    ys = [float(point[1]) / source_height for point in valid]
    left = min(xs)
    top = min(ys)
    return {
        "x": left,
        "y": top,
        "width": max(xs) - left,
        "height": max(ys) - top,
    }

/* ---- _scenario_frames_payload / _scenario_resource_payload (frames|image|video)  [wallpaper/scene_assets.py L277-L293] ---- */
def _scenario_frames_payload(port: int, directory: Path) -> dict:
    return {"type": "frames", "frames": _frame_urls(port, directory), "fps": _scenario_manifest_fps(directory)}


def _scenario_resource_payload(port: int, runtime_root: Path, resource: str) -> dict:
    rel = Path(str(resource or "").replace("\\", "/"))
    path = (runtime_root / rel).resolve()
    frame_dir = _first_frame_sequence_dir(path)
    if frame_dir is not None:
        return _scenario_frames_payload(port, frame_dir)
    if path.is_file():
        suffix = path.suffix.lower()
        if suffix in _SCENARIO_IMAGE_EXTS:
            return {"type": "image", "url": _asset_url(port, path)}
        if suffix in _SCENARIO_VIDEO_EXTS:
            return {"type": "video", "url": _asset_url(port, path)}
    return {"type": "missing", "resource": str(resource or "")}

/* ---- _prepare_scenario_payload: placementMode='crt_screen', sourceCropNorm, backplate  [wallpaper/scene_assets.py L393-L464] ---- */
def _prepare_scenario_payload(port: int) -> dict:
    src_root = _SCENARIO_SOURCE_ROOT
    runtime_graph = _RUNTIME_SCENARIOS / _SCENARIO_GRAPH_NAME
    if runtime_graph.exists():
        graph_path = runtime_graph
        backplate_source_root = _RUNTIME_SCENARIOS
        logger.info("[WallpaperAssets] using local scenario runtime pack: %s", _RUNTIME_SCENARIOS)
    elif src_root.exists():
        graph_path = _copy_scenario_pack(src_root, _RUNTIME_SCENARIOS)
        backplate_source_root = src_root
    else:
        graph_path = None
        backplate_source_root = _RUNTIME_SCENARIOS
    if graph_path is None or not graph_path.exists():
        return {"enabled": False, "reason": f"scenario graph not found: local={runtime_graph}, source={src_root}"}
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        logger.warning("[WallpaperAssets] failed to load scenario graph: %s", exc)
        return {"enabled": False, "reason": "scenario graph parse failed"}
    if (
        not isinstance(graph, dict)
        or not isinstance(graph.get("nodes"), list)
        or not isinstance(graph.get("edges"), list)
        or any(not isinstance(node, dict) for node in graph["nodes"])
        or any(not isinstance(edge, dict) for edge in graph["edges"])
    ):
        logger.warning("[WallpaperAssets] scenario graph has an invalid shape: %s", graph_path)
        return {"enabled": False, "reason": "scenario graph has an invalid shape"}

    node_resources = {}
    for node in graph.get("nodes", []):
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        node_resources[node_id] = _scenario_resource_payload(
            port,
            _RUNTIME_SCENARIOS,
            str(node.get("resource") or ""),
        )
    backplate, backplate_crop_norm = _prepare_scenario_backplate(backplate_source_root, _RUNTIME_SCENARIOS)
    static_hold_seconds = float(os.environ.get("AMADEUS_SCENARIO_STATIC_SECONDS", "45"))
    # Preserve explicit fixed intervals; the default ambient dwell is 45–60s.
    static_hold_max_seconds = static_hold_seconds if "AMADEUS_SCENARIO_STATIC_SECONDS" in os.environ else 60.0

    return {
        "enabled": True,
        "inactivitySeconds": float(os.environ.get("AMADEUS_SCENARIO_IDLE_SECONDS", "60")),
        "staticHoldSeconds": static_hold_seconds,
        "staticHoldMaxSeconds": static_hold_max_seconds,
        "enableFramePlayback": os.environ.get("AMADEUS_SCENARIO_FRAME_PLAYBACK", "1").strip().lower()
        not in {"0", "false", "no", "off"},
        "graph": graph,
        "resources": node_resources,
        "activities": {
            "work": {
                "entryLabel": "computer use",
                "labels": ["computer use"],
                "resourceHints": ["computer_use/computer_uses_mastered", "computer_uses_mastered"],
                "sceneIds": ["computer_use"],
                "keyboardSfxLabels": ["computer use"],
                "keyboardSfxResourceHints": ["computer_use/computer_uses_mastered", "computer_uses_mastered"],
                "holdDuringSpeech": True,
                "stayWithinActivity": True,
            },
        },
        "keyboardSfxUrl": _asset_url(port, _PROJECT_KEYBOARD_SFX) if _PROJECT_KEYBOARD_SFX.exists() else "",
        "backplateUrl": _asset_url(port, backplate) if backplate else "",
        "backplateCropNorm": backplate_crop_norm,
        "placementMode": "crt_screen",
        "sourceCropNorm": _SCENARIO_DEFAULT_SOURCE_CROP_NORM,
    }
