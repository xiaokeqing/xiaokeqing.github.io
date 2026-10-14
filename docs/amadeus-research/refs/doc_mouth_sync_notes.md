<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   docs/mouth_sync_system_notes.md
     quoted: L8-L24, L99-L140, L275-L321
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- goal + final direction  [docs/mouth_sync_system_notes.md L8-L24] ---- */
## Goal

The mouth-sync system should make SpriteForge speaking loops look closed-mouth during silence or TTS pauses without breaking the underlying high-frame-rate character animation.

The important constraint is that many current speaking loops are authored as "always speaking" loops. Even when TTS amplitude is zero, the base animation may still contain half-open or open-mouth frames. Therefore, silence cannot be handled by simply setting amplitude to zero and hoping the loop frame is visually closed.

## Final Direction

The final runtime strategy is:

1. Keep the original speaking loop playing normally.
2. During silence, overlay a closed-mouth patch on top of the current frame.
3. Clip that patch with a mouth-area mask so only the mouth region is replaced.
4. Track the mouth mask position per frame through `anchorTrack`.
5. Exclude transition nodes from mouth-sync entirely.

This is deliberately different from "jump to a closed frame". Jumping frames breaks motion continuity, especially in loops where hair, body, hand, or head are still moving.

/* ---- config model + silence_close mode + threshold  [docs/mouth_sync_system_notes.md L99-L140] ---- */
## Config Model

The runtime reads:

```text
assets/spriteforge/runtime/kurisu/spriteforge_mouth_config.json
```

Important fields:

- `profiles[label]`: per speaking-loop profile.
- `openness`: detected mouth openness for each frame.
- `anchor_track`: per-frame mouth anchor rectangle.
- `runtime_overlay_anchor`: geometry for the packaged KTX2 silence overlay.
- `mouth_set`: fallback mouth-set name.

The corresponding KTX2 overlay path lives in
`runtime_manifest.json::mouthOverlays`; runtime configuration contains no PNG
or authoring-workspace path.

The Python bridge converts these profiles into JS renderer configs in:

```text
render/spriteforge_animator.py::_load_mouth_configs
```

Current JS mode for SpriteForge speaking loops is:

```json
{
  "mode": "silence_close",
  "silenceThreshold": 0.08
}
```

In `silence_close` mode, the closed-mouth overlay is only visible when:

```text
!speaking || mouthValue <= silenceThreshold
```

When the character is actively speaking above threshold, the overlay is hidden and the authored speaking animation remains visible.

/* ---- JS renderer behaviour: mask ellipse math and overlay offsets  [docs/mouth_sync_system_notes.md L275-L321] ---- */
## JS Renderer Behavior

Relevant JS areas:

- `SpriteRenderer._updateMouthLayer`
- `SpriteRenderer._drawMouthMask`
- `SpriteRenderer._getMouthAnchor`
- `SpriteRenderer._isTextureReady`

The overlay is a child of the base sprite:

```js
this._mouthOverlay = new PIXI.Sprite();
this._mouthOverlay.anchor.set(0.5, 1.0);
this._mouthOverlay.mask = this._mouthMask;
this.sprite.addChild(this._mouthOverlay);
```

The mask is drawn in sprite-local coordinates. Anchor coordinates are interpreted relative to the texture center:

```text
localX = cx
localY = cy - textureHeight / 2
```

Default overlay alignment:

```text
overlay.x = currentAnchorX - sourceAnchorX
overlay.y = currentAnchorY - sourceAnchorY
```

Special case:

```text
overlayAlign = "canvas"
```

keeps the overlay at `(0, 0)` when the closed-mouth source is from the same canvas and should not be re-offset.

## Current Known Limitations

- Closed-frame quality is only as good as `closed_frame_idx` / `closed_source`.
- Some expressions still need visual review of the selected closed source.
- The system does not yet do high-quality continuous viseme mapping.
- It does not yet model mouth patch rotation or perspective.
- It assumes the mouth-area ellipse is enough; complex poses may need tighter polygon masks or manually authored masks.
