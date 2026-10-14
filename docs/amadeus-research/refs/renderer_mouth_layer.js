<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   render/web/renderer.js
     quoted: L827-L985
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- SpriteRenderer._hideMouthLayer / _updateMouthLayer / _isTextureReady / _textureHeight / _drawMouthMask / _getMouthAnchor  [render/web/renderer.js L827-L985] ---- */
    _hideMouthLayer() {
      this._frameStore.replacePins("mouth-display", []);
      if (this._mouthOverlay) {
        this._mouthOverlay.visible = false;
        this._mouthOverlay.x = 0;
        this._mouthOverlay.y = 0;
      }
      this._mouthSourceAnchor = null;
      if (this._mouthMask) this._mouthMask.clear();
    }

    _updateMouthLayer() {
      const cfg = this._mouthConfigs[this._currentEmotion];
      const textures = this._mouthTextures[this._currentEmotion] || [];
      if (!cfg || !textures.length) {
        this._hideMouthLayer();
        return;
      }

      const openness = Array.isArray(cfg.openness) ? cfg.openness : [];
      const n = Math.min(openness.length || textures.length, textures.length);
      if (n <= 0) {
        this._hideMouthLayer();
        return;
      }

      let bestIdx = 0;
      let bestDist = Infinity;
      const mode = cfg.mode || "full_map";
      const silenceClose = mode === "silence_close";
      const targetValue = silenceClose ? 0.0 : this._mouthValue;
      for (let i = 0; i < n; i++) {
        const level = typeof openness[i] === "number" ? openness[i] : (i / Math.max(1, n - 1));
        const dist = Math.abs(level - targetValue);
        if (dist < bestDist) {
          bestDist = dist;
          bestIdx = i;
        }
      }

      const texture = textures[bestIdx];
      if (!this._isTextureReady(texture)) {
        this._hideMouthLayer();
        return;
      }

      this._mouthOverlay.texture = texture;
      const mouthUrl = this._textureUrls.get(texture);
      this._frameStore.replacePins("mouth-display", mouthUrl ? [mouthUrl] : []);
      const sourceAnchors = Array.isArray(cfg.sourceAnchors) ? cfg.sourceAnchors : null;
      this._mouthSourceAnchor = sourceAnchors && sourceAnchors[bestIdx] ? sourceAnchors[bestIdx] : null;

      if (silenceClose) {
        const threshold = Number.isFinite(cfg.silenceThreshold) ? cfg.silenceThreshold : 0.08;
        const shouldClose = !this._speaking || this._mouthValue <= threshold;
        this._mouthOverlay.visible = shouldClose;
        if (shouldClose) {
          const maskAmp = Number.isFinite(cfg.silenceMaskAmplitude) ? cfg.silenceMaskAmplitude : 0.75;
          this._drawMouthMask(maskAmp, cfg);
        } else {
          this._hideMouthLayer();
        }
        return;
      }

      if (this._speaking) {
        this._mouthOverlay.visible = true;
        this._drawMouthMask(Math.max(this._mouthValue, 0.05), cfg);
      } else {
        this._mouthOverlay.visible = this._mouthValue > 0.01;
        if (this._mouthValue > 0.01) {
          this._drawMouthMask(Math.max(this._mouthValue, 0.05), cfg);
        } else {
          this._hideMouthLayer();
        }
      }
    }

    _isTextureReady(texture) {
      return !!(
        texture &&
        !texture.destroyed &&
        texture.baseTexture &&
        !texture.baseTexture.destroyed &&
        texture.baseTexture.valid &&
        Number.isFinite(texture.width) &&
        Number.isFinite(texture.height) &&
        texture.width > 1 &&
        texture.height > 1
      );
    }

    _textureHeight(texture, fallback = 1) {
      if (!this._isTextureReady(texture)) return fallback;
      return Number.isFinite(texture.height) && texture.height > 1 ? texture.height : fallback;
    }

    _drawMouthMask(amplitude, cfg) {
      const g = this._mouthMask;
      g.clear();
      if (amplitude <= 0) return;
      const tex = this.sprite.texture;
      const th = this._textureHeight(tex, 1);
      if (th <= 1) return;

      const anchor = this._getMouthAnchor(cfg);
      const cx = Number.isFinite(anchor.cx) ? anchor.cx : cfg.cx;
      const cy = Number.isFinite(anchor.cy) ? anchor.cy : cfg.cy;
      const width = Number.isFinite(anchor.width) ? anchor.width : cfg.width;
      const height = Number.isFinite(anchor.height) ? anchor.height : cfg.height;
      const maskWidthMul = Number.isFinite(cfg.maskWidthMul) ? cfg.maskWidthMul : 1.0;
      const maskHeightMul = Number.isFinite(cfg.maskHeightMul) ? cfg.maskHeightMul : 1.0;
      const maskCyOffset = Number.isFinite(cfg.maskCyOffset) ? cfg.maskCyOffset : 0.0;
      const overlayH = this._textureHeight(this._mouthOverlay.texture, th);

      const localX = cx;
      const localY = cy - th / 2;
      const maskLocalY = localY + maskCyOffset;
      const source = this._mouthSourceAnchor || {};
      const sourceCx = Number.isFinite(source.cx)
        ? source.cx
        : (Number.isFinite(cfg.sourceCx) ? cfg.sourceCx : (Number.isFinite(cfg.cx) ? cfg.cx : 0));
      const sourceCy = Number.isFinite(source.cy)
        ? source.cy
        : (Number.isFinite(cfg.sourceCy) ? cfg.sourceCy : (Number.isFinite(cfg.cy) ? cfg.cy : 0));
      if (cfg.overlayAlign === "canvas") {
        this._mouthOverlay.x = 0;
        this._mouthOverlay.y = 0;
      } else {
        this._mouthOverlay.x = localX - sourceCx;
        this._mouthOverlay.y = localY - (sourceCy - overlayH / 2);
      }

      const wHalf = (Math.max(1, width) / 2) * 1.8 * maskWidthMul;
      const hHalf = (Math.max(1, height) / 2) * (1.0 + 1.5 * amplitude) * maskHeightMul;
      if (hHalf < 0.5) return;

      g.beginFill(0xFFFFFF, 1);
      g.drawEllipse(localX, maskLocalY, wHalf, hHalf);
      g.endFill();
    }

    _getMouthAnchor(cfg) {
      const track = Array.isArray(cfg.anchorTrack) ? cfg.anchorTrack : [];
      if (track.length > 0) {
        const rawIdx = Number.isFinite(this._activeFrameIdx) ? this._activeFrameIdx : this._frameIdx;
        const idx = Math.max(0, Math.min(track.length - 1, Math.round(rawIdx)));
        const anchor = track[idx];
        if (anchor && typeof anchor === "object") {
          return {
            cx: Number.isFinite(anchor.cx) ? anchor.cx : cfg.cx,
            cy: Number.isFinite(anchor.cy) ? anchor.cy : cfg.cy,
            width: Number.isFinite(anchor.width) ? anchor.width : cfg.width,
            height: Number.isFinite(anchor.height) ? anchor.height : cfg.height,
          };
        }
      }
      return cfg || {};
    }
