<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   tools/detect_mouth_masks.py
     quoted: L44-L61, L94-L120, L184-L207, L210-L240, L300-L320
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- search-range constants  [tools/detect_mouth_masks.py L44-L61] ---- */

ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = ROOT / "render" / "assets" / "images"
OUTPUT_PATH = ROOT / "config" / "mouth_masks.json"

# Vertical mouth search range relative to the non-transparent sprite bounds.
# Half-body sprites: the head is roughly 0-40%, and the mouth is around 30-42%.
MOUTH_Y_RANGE = (0.28, 0.44)

# Horizontal mouth search range relative to the non-transparent sprite bounds.
# Restrict to the center area to avoid antialiasing noise from long side hair.
MOUTH_X_CENTER_RATIO = 0.30   # Only inspect this central width ratio.

# Pixel-difference threshold for the change map.
DIFF_THRESHOLD = 18

# Morphological cleanup kernel size.
MORPH_KERNEL = 5

/* ---- compute_mouth_roi: mouth box from inter-frame diff, sprite-centred coords  [tools/detect_mouth_masks.py L94-L120] ---- */
def compute_mouth_roi(frames: list[np.ndarray], binarize_thresh: float = 0.25):
    """
    Find the mouth region on the lower face using inter-frame differences.
    Returns (roi_mask, cx, cy, width, height, curve), with coordinates centered
    on the sprite origin.

    Strategy:
    - For <= 6 frames, diff all frames against the reference frame because
      subtle static expressions need a lower threshold.
    - For longer clips, compare only the first MAX_REF_FRAMES against frames[0]
      so large hair/clothing motion does not drown out the mouth signal.
    - Apply a hard size constraint: mouth width <= sprite_width * 0.18.
    """
    h, w = frames[0].shape[:2]

    # Find the overall non-transparent sprite bounds first.
    bbox = sprite_bbox(frames[0])
    if bbox is None:
        return None
    sy0, sy1, sx0, sx1 = bbox
    sh = sy1 - sy0   # Actual sprite height.
    sw = sx1 - sx0   # Actual sprite width.

    # Mouth search ROI: vertical ratio range plus a centered horizontal band.
    roi_y0 = sy0 + int(sh * MOUTH_Y_RANGE[0])
    roi_y1 = sy0 + int(sh * MOUTH_Y_RANGE[1])
    cx_sprite = (sx0 + sx1) // 2

/* ---- size clamps + cx_c/cy_c = centre-relative coordinates  [tools/detect_mouth_masks.py L184-L207] ---- */
    # Clamp the final dimensions.
    mw = min(mw, MAX_MOUTH_W)
    mh = min(mh, sh * 0.12)   # Mouth height <= 12% of sprite height.

    # Estimate upper-lip curvature from the upper contour points.
    pts = largest.reshape(-1, 2)
    top_thresh = ey - mh * 0.3
    top_pts = pts[pts[:, 1] < top_thresh + 4]
    curve = 0.0
    if len(top_pts) >= 4:
        try:
            coeffs = np.polyfit(top_pts[:, 0].astype(float),
                                top_pts[:, 1].astype(float), 2)
            raw_curve = float(coeffs[0]) * (mw ** 2) / max(mh, 1.0)
            curve = float(np.clip(raw_curve, -1.5, 1.5))
        except Exception:
            pass

    # Convert to a sprite-centered coordinate system.
    cx_c = ex - w / 2
    cy_c = ey - h / 2

    roi_mask = binary
    return roi_mask, float(cx_c), float(cy_c), float(mw), float(mh), float(curve)

/* ---- compute_frame_openness  [tools/detect_mouth_masks.py L210-L240] ---- */
def compute_frame_openness(frames: list[np.ndarray], roi_mask: np.ndarray) -> list[float]:
    """
    Compute each frame's ROI openness relative to a reference frame.
    Values are normalized to 0=closed and 1=max open. The reference is the
    frame with the smallest ROI variation, i.e. the most closed-looking frame.
    """
    h, w = frames[0].shape[:2]
    mask_3d = roi_mask.astype(bool)

    # Compute the RGB mean inside the ROI for each frame.
    def roi_mean(frame):
        rgb = frame[:, :, :3].astype(np.float32)
        return rgb[mask_3d].mean(axis=0) if mask_3d.any() else np.zeros(3)

    means = [roi_mean(f) for f in frames]

    # Use the frame closest to the median ROI color as the closed reference.
    mean_arr = np.array(means)          # (N, 3)
    median_val = np.median(mean_arr, axis=0)
    dists_to_median = np.linalg.norm(mean_arr - median_val, axis=1)
    ref_idx = int(np.argmin(dists_to_median))
    ref_mean = means[ref_idx]

    # L2 distance from the reference frame is the raw openness value.
    raw = np.array([np.linalg.norm(m - ref_mean) for m in means])
    max_val = raw.max()
    if max_val < 1e-6:
        return [0.0] * len(frames)

    openness = (raw / max_val).tolist()
    return openness

/* ---- closed_frame_idx = argmin(openness)  [tools/detect_mouth_masks.py L300-L320] ---- */
    # Save frame names for renderer-side loading.
    frame_names = [p.name for p in frame_paths]

    openness_arr = np.array(openness)
    closed_frame_idx = int(np.argmin(openness_arr))
    open_frame_idx = int(np.argmax(openness_arr))

    return {
        "cx": round(cx, 1),
        "cy": round(cy, 1),
        "width": round(width, 1),
        "height": round(height, 1),
        "curve": round(curve, 3),
        "closed_frame_idx": closed_frame_idx,
        "open_frame_idx": open_frame_idx,
        "frame_names": frame_names,
        "openness": [round(v, 4) for v in openness],
        # Internal-only data used for debug images.
        "_debug_frames": frames,
        "_debug_roi_mask": roi_mask,
    }
