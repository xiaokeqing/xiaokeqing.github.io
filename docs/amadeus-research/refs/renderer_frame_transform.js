<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   render/web/renderer.js
     quoted: L778-L825, L987-L1076
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- SpriteRenderer._applyFrame + _applyCurrentTransform (fit into CRT viewport)  [render/web/renderer.js L778-L825] ---- */
    _applyFrame(texture, video = null) {
      if (!texture) return;
      if (this._videoDisplay?.texture !== texture || this._videoDisplay?.source !== video) {
        if (video) video.retainDisplay(texture);
        this.sprite.texture = texture;
        this._releaseVideoDisplay();
        if (video) {
          this._videoDisplay = { source: video, texture, label: this._currentEmotion };
          this._frameVideoStats.videoDisplays++;
        }
      }
      this.sprite.texture = texture;
      const url = this._textureUrls.get(texture);
      if (url) this._frameStore.get(url);
      this._frameStore.replacePins("display", url ? [url] : []);
      this._applyCurrentTransform();
      this._updateMouthLayer();
    }

    _applyCurrentTransform() {
      const texture = this.sprite.texture;
      if (!texture || texture.height <= 1) {
        this.sprite.scale.set(1);
        return;
      }
      // Fit the character by the canvas it was authored on, not by this frame: a frame
      // wider than the canvas (hair blowing past its edge) must extend beyond it, centred
      // at the bottom like every other frame, instead of shrinking the character.
      const cfg = this._clipConfigs[this._currentEmotion] || {};
      const fitWidth = cfg.canvasWidth > 0 ? cfg.canvasWidth : texture.width;
      const fitHeight = cfg.canvasHeight > 0 ? cfg.canvasHeight : texture.height;
      if (this._viewportBounds) {
        const b = this._viewportBounds;
        const maxW = b.width * 0.64;
        const maxH = b.height * 0.90;
        const scale = Math.min(maxW / fitWidth, maxH / fitHeight);
        this.sprite.scale.set(scale);
        this.sprite.x = b.x + b.width * 0.52;
        // Keep the lower artwork just inside the CRT viewport.
        this.sprite.y = b.y + b.height - Math.max(3, b.height * 0.012);
        return;
      }
      const h = app.screen.height;
      const scale = h / fitHeight;
      this.sprite.scale.set(scale);
      this.sprite.x = app.screen.width / 2;
      this.sprite.y = h;
    }

/* ---- SpriteRenderer._startIdleTicker (frameIntervalMs clock, loopMode, cycle complete)  [render/web/renderer.js L987-L1076] ---- */
    _startIdleTicker() {
      // Uses per-emotion frame intervals when available (SpriteForge), falls back to 150ms.
      let elapsed = 0;
      let lastEmotion = null;
      let silentGuardHit = 0;
      let tickCount = 0;
      app.ticker.add((delta) => {
        tickCount++;
        if (tickCount % 180 === 1) {  // ~every 3s at 60fps
          console.log("[SpriteRenderer] ticker alive: tick=%d, iAE=%s, held=%s, tq=%d, emo=%s, fidx=%d, intv=%d, deltaMS=%d",
            tickCount, this._idleAnimationEnabled, this._held, this._transitionQueue.length,
            this._currentEmotion, this._frameIdx,
            this._frameIntervals[this._currentEmotion] || (this._clipConfigs[this._currentEmotion] && this._clipConfigs[this._currentEmotion].frameIntervalMs) || 150,
            Math.round(app.ticker.deltaMS));
        }

        if (!this._characterActive || !this._idleAnimationEnabled) { silentGuardHit++; return; }
        if (this._held) return;
        if (this._transitionQueue.length > 0) return;

        const frames = this._getEmotionFrames();
        if (!frames || frames.length === 0 || !(frames.some(Boolean) || this._hasReadyFrameVideo())) {
          silentGuardHit++;
          if (silentGuardHit === 60) {
            console.log("[SpriteRenderer] no frames for emotion: %s, keys: %s",
              this._currentEmotion, Object.keys(this._frames).join(','));
          }
          return;
        }
        silentGuardHit = 0;

        const emotion = this._currentEmotion;
        if (emotion !== lastEmotion) {
          elapsed = 0;
          lastEmotion = emotion;
        }
        const cfg = this._clipConfigs[emotion];
        const onceThenHold = cfg && cfg.loopMode === "once_then_hold";
        const mouthCfg = this._mouthConfigs[emotion];
        const interval = this._frameIntervals[emotion] || (cfg && cfg.frameIntervalMs) || 150;

        elapsed += Math.min(app.ticker.deltaMS, 100);
        if (elapsed < interval) return;
        const steps = this._textureSamplingEnabled
          ? Math.floor(elapsed / interval) : Math.min(4, Math.floor(elapsed / interval));
        elapsed -= steps * interval;

        let advanced = false;
        let crossedCycle = false;
        for (let i = 0; i < steps; i++) {
          if (onceThenHold && this._frameIdx >= frames.length - 1) {
            break;
          }

          const previousIdx = this._frameIdx;
          if (onceThenHold) {
            this._frameIdx = Math.min(this._frameIdx + 1, frames.length - 1);
          } else if (this._speaking && mouthCfg && frames.length > 1) {
            this._frameIdx = (this._frameIdx + 1) % frames.length;
          } else if (this._speaking && frames.length > 1) {
            this._frameIdx = (this._frameIdx % (frames.length - 1)) + 1;
          } else {
            this._frameIdx = (this._frameIdx + 1) % frames.length;
          }
          if (!onceThenHold && this._frameIdx <= previousIdx) crossedCycle = true;
          advanced = true;
        }

        if (!advanced) {
          return;
        }

        if (this._textureSamplingEnabled) this._sampleTimeMs = this._frameIdx * interval + elapsed;
        this._showFrame(this._frameIdx);
        if (onceThenHold && this._frameIdx >= frames.length - 1) {
          this._notifyCycleComplete(emotion);
        } else if (!onceThenHold && (this._textureSamplingEnabled ? crossedCycle : this._frameIdx === 0)) {
          if (this._textureSamplingEnabled) this._cycleCompletedForEmotion = "";
          this._notifyCycleComplete(emotion);
        } else {
          this._cycleCompletedForEmotion = "";
        }
        if (this._frameIdx === 0) {
          console.log("[SpriteRenderer] looping: emotion=%s frames=%d interval=%d",
            emotion, frames.length, interval);
        }
      });

      console.log("[SpriteRenderer] idle ticker started");
    }
