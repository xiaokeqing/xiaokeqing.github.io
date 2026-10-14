<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   render/web/wallpaper_scene.js
     quoted: L12-L25, L649-L706, L2097-L2169
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- coverTransform - the single wallpaper-art -> screen transform  [render/web/wallpaper_scene.js L12-L25] ---- */
  // The wallpaper art keeps its proportions on every screen: it covers the screen like a
  // desktop "fill" wallpaper and crops what overflows instead of stretching, so 16:9 art on
  // a 16:10 laptop loses a strip at each side. This one transform places the art's sprites
  // and maps its image coordinates (CRT polygon, lamp and ambient positions) to the screen.
  function coverTransform(imageWidth, imageHeight, screenWidth, screenHeight) {
    const scale = Math.max(screenWidth / imageWidth, screenHeight / imageHeight);
    return {
      scale,
      x: (screenWidth - imageWidth * scale) / 2,
      y: (screenHeight - imageHeight * scale) / 2,
      width: imageWidth * scale,
      height: imageHeight * scale,
    };
  }

/* ---- scenarioRuntime.layout + _syncLayerOrder (the real z-order)  [render/web/wallpaper_scene.js L649-L706] ---- */
    layout(bounds, mask) {
      if (!this.container || !this.sprite) return;
      this._syncLayerOrder();
      this.container.mask = mask || null;
      if (this.backplateSprite) {
        this.backplateSprite.mask = mask || null;
        this._placeSpriteIn(this.backplateSprite, bounds);
      }
      this._placeSprite(bounds);
    },

    _syncLayerOrder() {
      if (!this.app || !this.app.stage) return;
      const stage = this.app.stage;
      const renderApp = window.renderApp || {};
      const spriteLayer = renderApp._sprite && renderApp._sprite.container;
      const live2dLayer = renderApp.getModelCharacterContainer && renderApp.getModelCharacterContainer();
      const subtitleLayer = wallpaperSubtitle && wallpaperSubtitle.container;
      const characterLayers = [spriteLayer, live2dLayer].filter((layer) => layer && stage.children.includes(layer));

      if (this.backplateSprite && stage.children.includes(this.backplateSprite)) {
        stage.removeChild(this.backplateSprite);
      }
      if (subtitleLayer && stage.children.includes(subtitleLayer)) {
        stage.removeChild(subtitleLayer);
      }
      if (this.container && stage.children.includes(this.container)) {
        stage.removeChild(this.container);
      }

      const bgIndex = this.backplateSprite ? stage.children.indexOf(desktopScene.bg) : -1;
      const characterIndexes = characterLayers
        .map((layer) => stage.children.indexOf(layer))
        .filter((index) => index >= 0);
      const characterBottomIndex = characterIndexes.length ? Math.min.apply(null, characterIndexes) : -1;
      const characterTopIndex = characterIndexes.length ? Math.max.apply(null, characterIndexes) : -1;
      const backplateIndex = characterBottomIndex >= 0 ? characterBottomIndex : Math.max(0, bgIndex + 1);
      if (this.backplateSprite) {
        stage.addChildAt(this.backplateSprite, Math.min(backplateIndex, stage.children.length));
      }

      const refreshedCharacterTopIndex = characterLayers
        .map((layer) => stage.children.indexOf(layer))
        .filter((index) => index >= 0)
        .reduce((max, index) => Math.max(max, index), characterTopIndex >= 0 ? characterTopIndex : -1);
      if (subtitleLayer) {
        const subtitleIndex = refreshedCharacterTopIndex >= 0 ? refreshedCharacterTopIndex + 1 : stage.children.length;
        stage.addChildAt(subtitleLayer, Math.min(subtitleIndex, stage.children.length));
      }

      const refreshedSubtitleIndex = subtitleLayer ? stage.children.indexOf(subtitleLayer) : -1;
      const scenarioIndex = refreshedSubtitleIndex >= 0
        ? refreshedSubtitleIndex + 1
        : (refreshedCharacterTopIndex >= 0 ? refreshedCharacterTopIndex + 1 : stage.children.length);
      if (this.container) {
        stage.addChildAt(this.container, Math.min(scenarioIndex, stage.children.length));
      }
    },

/* ---- desktopScene._imageTransform/_crtPoints/_computeBounds/layout (CRT polygon + mask)  [render/web/wallpaper_scene.js L2097-L2169] ---- */
    _imageTransform() {
      const screen = this.app.screen;
      const imgSize = this.cfg.img_size || [screen.width, screen.height];
      return coverTransform(Math.max(1, Number(imgSize[0]) || 1), Math.max(1, Number(imgSize[1]) || 1),
        screen.width, screen.height);
    },

    _placeBackdrop(sprite) {
      if (!sprite) return;
      const t = this._imageTransform();
      sprite.x = t.x;
      sprite.y = t.y;
      sprite.width = t.width;
      sprite.height = t.height;
    },

    _crtPoints() {
      const app = this.app;
      const rawPoints = this.cfg.crt_polygon || this.cfg.crt_corners || [
        [0, 0],
        [app.screen.width, 0],
        [app.screen.width, app.screen.height],
        [0, app.screen.height],
      ];
      const t = this._imageTransform();
      return rawPoints.map((p) => ({ x: Number(p[0]) * t.scale + t.x, y: Number(p[1]) * t.scale + t.y }));
    },

    _computeBounds(points) {
      const xs = points.map((p) => p.x);
      const ys = points.map((p) => p.y);
      const x = Math.min(...xs);
      const y = Math.min(...ys);
      const right = Math.max(...xs);
      const bottom = Math.max(...ys);
      return { x, y, width: right - x, height: bottom - y, right, bottom };
    },

    layout() {
      if (!this.app || !this.mask || !this.staticOverlay) return;
      this._placeBackdrop(this.bg);
      this._placeBackdrop(this.ambientLowSprite);
      this._placeBackdrop(this.ambientSprite);

      const points = this._crtPoints();
      const bounds = this._computeBounds(points);
      this._points = points;
      this._crtBounds = bounds;

      this.mask.clear();
      this.mask.beginFill(0xffffff, 1);
      this.mask.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i += 1) this.mask.lineTo(points[i].x, points[i].y);
      this.mask.lineTo(points[0].x, points[0].y);
      this.mask.endFill();

      this.staticOverlay.clear();
      this._drawPolygon(this.staticOverlay, points, 0x07121c, 0.10);

      callRender("setCharacterViewportBounds", [bounds]);
      scenarioRuntime.layout(bounds, this.mask);
      wallpaperSubtitle.layout(bounds);
      this.bottomVignette.width = bounds.width * 0.76;
      this.bottomVignette.height = bounds.height * 0.085;
      this.bottomVignette.x = bounds.x + bounds.width * 0.52 - this.bottomVignette.width / 2;
      this.bottomVignette.y = bounds.bottom - this.bottomVignette.height / 2;
      wallpaperSubtitle.updateVisibility();
      if (this.canvasSurface && typeof this.canvasSurface.layout === "function") {
        this.canvasSurface.layout(bounds);
      }
      this._drawGlow();
      this._drawScanlineNoise();
    },
