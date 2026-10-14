<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   render/web/wallpaper_scene.js
     quoted: L1604-L1634, L1667-L1699
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- _activeSourceCrop / _textureForBase - normalized source crop  [render/web/wallpaper_scene.js L1604-L1634] ---- */
    _activeSourceCrop(base, cropNormOverride) {
      if (!base || !base.baseTexture || !base.baseTexture.valid) return null;
      const bw = Math.max(1, base.baseTexture.width || 1);
      const bh = Math.max(1, base.baseTexture.height || 1);
      const cropNorm = cropNormOverride === undefined ? this.sourceCropNorm : cropNormOverride;
      if (cropNorm && cropNorm.length >= 4) {
        return [
          Number(cropNorm[0]) * bw,
          Number(cropNorm[1]) * bh,
          Number(cropNorm[2]) * bw,
          Number(cropNorm[3]) * bh,
        ];
      }
      return this.sourceCrop && this.sourceCrop.length >= 4 ? this.sourceCrop : null;
    },

    _textureForBase(base, cropNormOverride) {
      const crop = this._activeSourceCrop(base, cropNormOverride);
      if (!crop || crop.length < 4 || !base.baseTexture.valid) return base;
      const sx = Math.max(0, Number(crop[0]) || 0);
      const sy = Math.max(0, Number(crop[1]) || 0);
      const sw = Math.max(1, Number(crop[2]) || (base.baseTexture.width - sx));
      const sh = Math.max(1, Number(crop[3]) || (base.baseTexture.height - sy));
      const frame = new PIXI.Rectangle(
        Math.min(sx, Math.max(0, base.baseTexture.width - 1)),
        Math.min(sy, Math.max(0, base.baseTexture.height - 1)),
        Math.min(sw, Math.max(1, base.baseTexture.width - sx)),
        Math.min(sh, Math.max(1, base.baseTexture.height - sy))
      );
      return new PIXI.Texture(base.baseTexture, frame);
    },

/* ---- _placeSpriteIn / _stretchSprite (crt_screen) / _fitSprite  [render/web/wallpaper_scene.js L1667-L1699] ---- */
    _placeSprite(bounds) {
      if (!this.sprite || !bounds || !this.sprite.texture) return;
      this._placeSpriteIn(this.sprite, bounds);
    },

    _placeSpriteIn(sprite, bounds) {
      if (!sprite || !bounds || !sprite.texture) return;
      if (this.placementMode === "crt_screen") {
        this._stretchSprite(sprite, bounds);
      } else {
        this._fitSprite(sprite, bounds);
      }
    },

    _stretchSprite(sprite, bounds) {
      const tex = sprite.texture;
      const tw = Math.max(1, tex.width || tex.orig?.width || 1);
      const th = Math.max(1, tex.height || tex.orig?.height || 1);
      sprite.scale.set(bounds.width / tw, bounds.height / th);
      sprite.x = bounds.x;
      sprite.y = bounds.y;
    },

    _fitSprite(sprite, bounds) {
      if (!sprite || !bounds || !sprite.texture) return;
      const tex = sprite.texture;
      const tw = Math.max(1, tex.width || tex.orig?.width || 1);
      const th = Math.max(1, tex.height || tex.orig?.height || 1);
      const scale = Math.max(bounds.width / tw, bounds.height / th);
      sprite.scale.set(scale);
      sprite.x = bounds.x + (bounds.width - tw * scale) / 2;
      sprite.y = bounds.y + (bounds.height - th * scale) / 2;
    },
