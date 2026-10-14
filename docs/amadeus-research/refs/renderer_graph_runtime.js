<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   render/web/renderer.js
     quoted: L115-L125, L394-L397, L1137-L1163, L1342-L1386, L1534-L1549, L1915-L1928
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- mouth overlay/mask creation as children of the base sprite  [render/web/renderer.js L115-L125] ---- */
      this._mouthMask = new PIXI.Graphics();
      this.sprite.addChild(this._mouthMask);

      this._mouthOverlay = new PIXI.Sprite();
      this._mouthOverlay.anchor.set(0.5, 1.0);
      this._mouthOverlay.x = 0;
      this._mouthOverlay.y = 0;
      this._mouthOverlay.visible = false;
      this._mouthOverlay.mask = this._mouthMask;
      this.sprite.addChild(this._mouthOverlay);
      this._mouthConfigs = {};     // label → js_cfg

/* ---- setMouth  [render/web/renderer.js L394-L397] ---- */
    setMouth(value) {
      this._mouthValue = Math.max(0, Math.min(1, value));
      this._updateMouthLayer();
    }

/* ---- SpriteForgeRuntime.loadGraph  [render/web/renderer.js L1137-L1163] ---- */
    loadGraph(payload) {
      const signature = JSON.stringify(payload || {});
      if (this._graphSignature === signature && this.currentNodeId) {
        return;
      }
      this._graphSignature = signature;
      this.graph = payload.graph || { nodes: [], edges: [] };
      this.rootNodeId = payload.rootNodeId || null;
      this.nodeDurations = payload.durations || {};
      this.cfg = payload.config || {};
      this.lastSpeechEndedAt = this.speechActive ? null : Date.now();
      this.nodesById = {};
      this.labelToIds = {};
      for (const node of this.graph.nodes || []) {
        this.nodesById[node.id] = node;
        const label = node.label || "";
        if (!this.labelToIds[label]) this.labelToIds[label] = [];
        this.labelToIds[label].push(node.id);
        if (!this.rootNodeId && node.isRoot) this.rootNodeId = node.id;
      }
      if (!this.rootNodeId && this.graph.nodes && this.graph.nodes.length) {
        this.rootNodeId = this.graph.nodes[0].id;
      }
      if (this.rootNodeId) this._playNode(this.rootNodeId);
      this._prefetchGraphEntries();
      console.log("[SpriteForgeRuntime] graph loaded:", (this.graph.nodes || []).length, "nodes");
    }

/* ---- onCycleComplete / _advanceNow / _playNode  [render/web/renderer.js L1342-L1386] ---- */
    onCycleComplete(label) {
      if (label !== this._label(this.currentNodeId)) return;
      if (!this.speechActive && this._has("transitionHoldLabels", label)) {
        this.transitionHoldActive = true;
        this.sprite.holdFrame(-1);
        return;
      }
      this._advanceNow();
    }

    _advanceNow() {
      if (this.forcedNodeId) {
        const nodeId = this.forcedNodeId;
        this.forcedNodeId = null;
        this._playNode(nodeId);
        return;
      }
      if (this.pendingExpression) {
        const label = this.pendingExpression;
        this.pendingExpression = null;
        const entry = this._findTriggerEntry(label);
        if (entry) {
          this._playNode(entry);
          return;
        }
        const target = this._nodeByLabel(label);
        if (target) {
          this._playNode(target.id);
          return;
        }
        console.warn("[SpriteForgeRuntime] no trigger entry for:", label);
      }
      const next = this._nextAutoNode(this.currentNodeId);
      if (next) this._playNode(next);
    }

    _playNode(nodeId) {
      if (!nodeId || !this.nodesById[nodeId]) return;
      this.currentNodeId = nodeId;
      this.transitionHoldActive = false;
      this.sprite.clearHold();
      const label = this._label(nodeId);
      this.sprite.setEmotion(label);
      this._prefetchNodeNeighborhood(nodeId);
    }

/* ---- _nextAutoNode (prob-weighted traversal)  [render/web/renderer.js L1534-L1549] ---- */
    _nextAutoNode(fromId) {
      const standbyAllowed = !this.speechActive && this.lastSpeechEndedAt !== null
        && Date.now() - this.lastSpeechEndedAt >= Number(this.cfg.idleStandbyDelaySec ?? 30) * 1000;
      // Gate only automatic side entry; explicit expression paths still use
      // the authored graph and speech can interrupt without waiting.
      const edges = (this.graph.edges || []).filter((e) => e.from === fromId && Number(e.prob || 0) > 0
        && (standbyAllowed || this._label(e.to) !== (this.cfg.idleStandbyEntryLabel || "trans_standby")));
      if (!edges.length) return fromId;
      const total = edges.reduce((sum, e) => sum + Number(e.prob || 0), 0);
      let r = Math.random() * total;
      for (const edge of edges) {
        r -= Number(edge.prob || 0);
        if (r <= 0) return edge.to;
      }
      return edges[edges.length - 1].to;
    }

/* ---- viewport bounds + CRT polygon mask application  [render/web/renderer.js L1915-L1928] ---- */
    setCharacterViewportBounds(bounds) {
      this._characterViewport = bounds || null;
      this._sprite.setViewportBounds(bounds);
      this._modelAdapter?.setViewport(bounds);
    }

    setCharacterViewportMask(mask) {
      this._sprite.container.mask = mask || null;
      this._modelContainer.mask = mask || null;
    }

    getModelCharacterContainer() { return this._modelContainer; }

    getCharacterLayers() { return [this._sprite.container, this._modelContainer]; }
