<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   render/spriteforge_animator.py
     quoted: L552-L638
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- _load_mouth_configs (config -> JS cfg: mode/silenceThreshold/sourceAnchors/anchorTrack)  [render/spriteforge_animator.py L552-L638] ---- */
    def _load_mouth_configs(self) -> None:
        if not MOUTH_MASKS_ENABLED:
            logger.info("[SFAnimator] mouth masks disabled globally for graph test")
            return
        pack = self._character_pack
        if pack is None:
            return
        raw = pack.mouth_config
        expressions = raw.get("expressions", {})
        profiles = raw.get("profiles", {})
        if not isinstance(profiles, dict) or not profiles:
            logger.warning("[SFAnimator] mouth config has no v2 speaking profiles")
            return

        def _build(expr_cfg: dict) -> dict | None:
            if not isinstance(expr_cfg, dict):
                return None
            return {
                "cx":     expr_cfg.get("cx", 0.0),
                "cy":     expr_cfg.get("cy", 0.0),
                "width":  expr_cfg.get("width", 40.0),
                "height": expr_cfg.get("height", 20.0),
                "curve":  expr_cfg.get("curve", 0.2),
                "sourceCx": expr_cfg.get("cx", 0.0),
                "sourceCy": expr_cfg.get("cy", 0.0),
                "closedFrameIdx": 0,
            }

        mouth_sets = {name: _build(cfg) for name, cfg in expressions.items()}

        loaded = 0
        for label, profile in profiles.items():
            if not isinstance(profile, dict):
                continue
            if label not in _MOUTH_SYNC_LABELS:
                logger.info("[SFAnimator] mouth profile ignored for transition/non-speaking node: %s", label)
                continue
            mouth_set = str(profile.get("mouth_set") or "neutral")
            base_js = mouth_sets.get(mouth_set)
            overlay_paths = pack.mouth_overlay_paths.get(label, ())
            if not base_js or not overlay_paths:
                logger.warning("[SFAnimator] mouth profile skipped (missing set=%s): %s",
                               mouth_set, label)
                continue
            frame_urls = [self._url(path) for path in overlay_paths]
            js_cfg = dict(base_js)
            js_cfg["mode"] = "silence_close"
            js_cfg["silenceThreshold"] = 0.08
            js_cfg.update(_MOUTH_SILENCE_MASK_OVERRIDES.get(label, {}))
            js_cfg["profile"] = label
            js_cfg["cx"] = profile.get("cx", js_cfg["cx"])
            js_cfg["cy"] = profile.get("cy", js_cfg["cy"])
            js_cfg["width"] = profile.get("width", js_cfg["width"])
            js_cfg["height"] = profile.get("height", js_cfg["height"])
            js_cfg["opennessByFrame"] = profile.get("openness", [])
            js_cfg["closedFrameIdx"] = 0
            js_cfg["frameUrls"] = frame_urls
            js_cfg["openness"] = [0.0 for _ in frame_urls]
            raw_overlay_anchor = profile.get("runtime_overlay_anchor")
            overlay_anchor = raw_overlay_anchor if isinstance(raw_overlay_anchor, dict) else {}
            source_anchor = {
                "cx": overlay_anchor.get("cx", profile.get("cx", js_cfg["cx"])),
                "cy": overlay_anchor.get("cy", profile.get("cy", js_cfg["cy"])),
                "width": overlay_anchor.get("width", profile.get("width", js_cfg["width"])),
                "height": overlay_anchor.get("height", profile.get("height", js_cfg["height"])),
            }
            js_cfg["sourceAnchors"] = [source_anchor]
            js_cfg["sourceCx"] = source_anchor["cx"]
            js_cfg["sourceCy"] = source_anchor["cy"]
            anchor_track = []
            for item in profile.get("anchor_track", []) or []:
                if not isinstance(item, dict):
                    continue
                anchor_track.append({
                    "cx": item.get("cx", js_cfg["cx"]),
                    "cy": item.get("cy", js_cfg["cy"]),
                    "width": item.get("width", js_cfg["width"]),
                    "height": item.get("height", js_cfg["height"]),
                    "score": item.get("score", 0.0),
                })
            js_cfg["anchorTrack"] = anchor_track
            self.engine.load_mouth_config(label, js_cfg)
            loaded += 1
            logger.info("[SFAnimator] mouth profile: %s -> %s (%d anchors, %d overlay frames)",
                        label, mouth_set, len(anchor_track), len(frame_urls))

        logger.info("[SFAnimator] mouth profiles loaded: %d", loaded)
