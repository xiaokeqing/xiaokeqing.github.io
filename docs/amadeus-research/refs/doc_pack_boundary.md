<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   docs/character_pack_authoring.md
     quoted: L1-L30
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- runtime-only pack contract; authoring projects/PNG/video are not part of it  [docs/character_pack_authoring.md L1-L30] ---- */
# Runtime character-pack contract

Amadeus consumes a runtime-only character pack. SpriteForge or another authoring
tool may produce that pack, but authoring projects, PNG sequences, source video,
interpolation output, and editor layout data are not part of the runtime format.

The currently supported format identifier is:

```text
amadeus.spriteforge.character-pack.v1
```

Machine-readable schemas live in `schemas/character-pack-v1/`. Cross-file rules
that JSON Schema cannot express are enforced by `tools/validate_character_pack.py`
and by the runtime pack loader.

## Package layout

```text
character-pack/
  runtime_manifest.json
  graph_config.json
  spriteforge_mouth_config.json
  textures/
    ... .ktx2
```

All paths in the manifest are forward-slash-compatible paths relative to the
pack root. Absolute paths and `..` traversal are rejected. Runtime JSON must not
contain SpriteForge workspace paths or PNG frame references.
