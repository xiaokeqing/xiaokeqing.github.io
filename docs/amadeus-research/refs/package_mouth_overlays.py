<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   tools/package_spriteforge_character.py
     quoted: L82-L100, L245-L325
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- ONCE_THEN_HOLD_LABELS / POST_EMOTION_ROOTS / PREFER_OWN_CLOSED_FRAME  [tools/package_spriteforge_character.py L82-L100] ---- */
ONCE_THEN_HOLD_LABELS = {
    "trans_standby",
    "speaking_trans",
    "closed_eye_trans",
    "thinking_trans",
    "thinking_to_serious",
    "thinking_to_key_point",
    "serious_to_thinking",
    "trans_smile",
    "sad_trans",
    "shy_trans",
    "surprise_trans",
    "angry_trans",
}
POST_EMOTION_ROOTS = {
    "smile": Path("projects") / "kurisu_smile_loop" / "frames_alpha_2x_gmfss" / "idle",
    "sad": Path("projects") / "kurisu_sad_idle_loop" / "frames_alpha_2x_gmfss" / "idle",
}
PREFER_OWN_CLOSED_FRAME = {"key_point_speaking", "thinking_speaking2"}

/* ---- _mouth_runtime_config: the silence overlay IS one authored PNG frame -> one KTX2  [tools/package_spriteforge_character.py L245-L325] ---- */
def _mouth_runtime_config(
    workspace: Path,
    raw: dict[str, Any],
    suffix: str,
) -> tuple[dict[str, Any], dict[str, tuple[Path, dict[str, Any]]]]:
    expressions: dict[str, Any] = {}
    for name, raw_expression in (raw.get("expressions") or {}).items():
        if not isinstance(raw_expression, dict):
            continue
        expressions[str(name)] = {
            key: value
            for key, value in raw_expression.items()
            if key != "speaking_frames"
        }

    profiles: dict[str, Any] = {}
    overlays: dict[str, tuple[Path, dict[str, Any]]] = {}
    for raw_label, raw_profile in (raw.get("profiles") or {}).items():
        label = str(raw_label)
        if not isinstance(raw_profile, dict):
            continue
        profile = {
            key: value
            for key, value in raw_profile.items()
            if key not in {"root", "phase", "frame_names", "closed_source", "frame_count"}
        }
        names = raw_profile.get("frame_names") or []
        anchors = raw_profile.get("anchor_track") or []
        try:
            closed_index = int(raw_profile.get("closed_frame_idx", 0))
        except (TypeError, ValueError):
            closed_index = 0
        closed_source = raw_profile.get("closed_source")
        use_closed_source = (
            isinstance(closed_source, dict) and label not in PREFER_OWN_CLOSED_FRAME
        )
        if use_closed_source:
            assert isinstance(closed_source, dict)
            source = _authoring_path(
                workspace,
                closed_source.get("root"),
                closed_source.get("phase"),
                closed_source.get("frame_name"),
            )
            anchor = closed_source.get("anchor")
            anchor = dict(anchor) if isinstance(anchor, dict) else {}
        else:
            if not isinstance(names, list) or not 0 <= closed_index < len(names):
                raise ValueError(f"mouth profile {label!r} has no valid closed frame")
            source = _authoring_path(
                workspace,
                raw_profile.get("root"),
                raw_profile.get("phase"),
                names[closed_index],
            )
            raw_anchor = anchors[closed_index] if 0 <= closed_index < len(anchors) else {}
            anchor = dict(raw_anchor) if isinstance(raw_anchor, dict) else {}
        texture = _sidecar(source, suffix)
        # An explicit source is a visually selected closed mouth. The loop's
        # minimum openness score may still be an open mouth; it is not an
        # equivalent fallback when that source has not been encoded.
        if not texture.is_file() or texture.stat().st_size <= 0:
            raise ValueError(f"mouth profile {label!r} is missing KTX2 overlay: {texture}")
        runtime_anchor = {
            "cx": anchor.get("cx", raw_profile.get("cx", 0.0)),
            "cy": anchor.get("cy", raw_profile.get("cy", 0.0)),
            "width": anchor.get("width", raw_profile.get("width", 40.0)),
            "height": anchor.get("height", raw_profile.get("height", 20.0)),
        }
        profile["runtime_overlay_anchor"] = runtime_anchor
        profiles[label] = profile
        overlays[label] = (texture, runtime_anchor)

    runtime = {
        "version": raw.get("version"),
        "canvas_size": raw.get("canvas_size"),
        "profile_kind": "runtime_ktx2",
        "expressions": expressions,
        "profiles": profiles,
    }
    return runtime, overlays
