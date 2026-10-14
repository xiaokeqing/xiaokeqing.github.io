<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   assets/README.md
     quoted: L96-L104
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- assets are read-only input; SpriteForge PNGs/videos stay out of Amadeus  [assets/README.md L96-L104] ---- */
- `assets/` is read-only application input. Generated output belongs in
  `runtime/`, `output/`, or another explicitly writable state directory.
- The root AGPL-3.0 license covers Amadeus first-party code and modifications,
  not character, voice, model, reference-audio, or other external media packs.
- The external bundle mechanism is a transport and integrity boundary, not a
  copyright grant. Only distribute packs whose rights have been reviewed.
- SpriteForge authoring PNGs, videos, interpolation output, and QA renders stay
  in SpriteForge or another source workspace. Amadeus consumes only the runtime
  manifest, graph, mouth config, and indexed KTX2 textures.
