<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   render/spriteforge_animator.py
     quoted: L42-L162
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- label sets, mouth-sync label filter, silence-mask overrides, hold constants  [render/spriteforge_animator.py L42-L162] ---- */
_SPEAKING_TRIGGER_LABEL = "speaking_trans"
_DEFAULT_SPEAKING_TRIGGER_LABEL = "speaking_short"
_CLOSED_EYE_SPEAKING_TRIGGER_LABEL = "closed_eye_trans"
_CLOSED_EYE_SPEAKING_CHANCE = 0.18
_SERIOUS_SPEAKING_LABELS = {"speaking_trans", "speaking_loop1", "speaking_loop2"}
_DEFAULT_SPEAKING_LABELS = {"speaking_short", "speaking_med", "speaking_long"}
_CLOSED_EYE_SPEAKING_LABELS = {
    "closed_eye_trans",
    "speaking_closed_eye_1",
    "speaking_closed_eye_2",
}
_CLOSED_EYE_SPEAKING_ELIGIBLE_LABELS = {
    "idle",
    "idle1",
    "idle2",
    "idle_mic_wind",
    "idle_str_wind",
    "idle_closed_eye",
    *_DEFAULT_SPEAKING_LABELS,
}
_IDLE_STANDBY_ENTRY_LABEL = "trans_standby"
IDLE_STANDBY_DELAY_SEC = 30.0
_THINKING_SPEAKING_LABELS = {"thinking_speaking1", "thinking_speaking2", "key_point_speaking"}
_THINKING_ENTRY_LABELS = {"thinking_trans", "thinking_to_serious", "thinking_to_key_point"}
_SERIOUS_ENTRY_LABELS = {"speaking_trans", "thinking_to_serious"}
_SERIOUS_EXIT_LABELS = {"serious_to_thinking"}
_EMOTION_SPEAKING_ENTRY_BY_INTENT = {
    "smile": "trans_smile",
    "sad": "sad_trans",
    "shy": "shy_trans",
    "surprise": "surprise_trans",
    "angry": "angry_trans",
}
_EMOTION_SPEAKING_INTENT_BY_LABEL = {
    "smile": "smile",
    "trans_smile": "smile",
    "smile_speaking": "smile",
    "sad": "sad",
    "sad_trans": "sad",
    "sad_speaking": "sad",
    "shy": "shy",
    "shy_trans": "shy",
    "shy_speaking1": "shy",
    "shy_speaking2": "shy",
    "surprised": "surprise",
    "surprise": "surprise",
    "surprise_trans": "surprise",
    "surprise_speaking": "surprise",
    "angry": "angry",
    "angry_trans": "angry",
    "angry_speaking": "angry",
}
_EMOTION_SPEAKING_LABELS = {
    "smile_speaking",
    "sad_speaking",
    "shy_speaking1",
    "shy_speaking2",
    "surprise_speaking",
    "angry_speaking",
}
_POST_SPEECH_EMOTION_LABEL_BY_INTENT = {
    "smile": "smile",
    "sad": "sad",
}
_RUNTIME_POST_EMOTION_LABELS = ("smile", "sad")
_SPEAKING_PERFORMANCE_LABELS = (
    _SERIOUS_SPEAKING_LABELS
    | _DEFAULT_SPEAKING_LABELS
    | _CLOSED_EYE_SPEAKING_LABELS
    | _THINKING_SPEAKING_LABELS
    | _EMOTION_SPEAKING_LABELS
)
# Entry transitions are visual graph hops. They may be part of a speaking route,
# but they are not mouth-sync loops and must not inherit mouth masks.
_SPEAKING_ENTRY_TRANSITION_LABELS = (
    {_SPEAKING_TRIGGER_LABEL, _CLOSED_EYE_SPEAKING_TRIGGER_LABEL}
    | _THINKING_ENTRY_LABELS
    | _SERIOUS_EXIT_LABELS
    | set(_EMOTION_SPEAKING_ENTRY_BY_INTENT.values())
)
# Mouth sync belongs only to new SpriteForge speaking-loop assets. Legacy/static
# post-emotion resources are intentionally kept outside this path.
_MOUTH_SYNC_LABELS = _SPEAKING_PERFORMANCE_LABELS - _SPEAKING_ENTRY_TRANSITION_LABELS
_MOUTH_SILENCE_MASK_OVERRIDES = {
    "key_point_speaking": {
        "overlayAlign": "canvas",
        "preferOwnClosedFrame": True,
        "silenceMaskAmplitude": 0.80,
        "maskWidthMul": 1.00,
        "maskHeightMul": 0.90,
        "maskCyOffset": 0.0,
    },
    "thinking_speaking2": {
        "silenceMaskAmplitude": 1.0,
        "maskWidthMul": 1.04,
        "maskHeightMul": 1.25,
        "maskCyOffset": -4.0,
    },
}
_NON_EMOTION_SPEAKING_LABELS = (
    _SERIOUS_SPEAKING_LABELS
    | _DEFAULT_SPEAKING_LABELS
    | _CLOSED_EYE_SPEAKING_LABELS
    | _THINKING_SPEAKING_LABELS
    | _THINKING_ENTRY_LABELS
    | _SERIOUS_EXIT_LABELS
)
_SPEAKING_RELEASE_LABELS = (
    _SPEAKING_PERFORMANCE_LABELS
    | _THINKING_ENTRY_LABELS
    | _SERIOUS_EXIT_LABELS
    | set(_EMOTION_SPEAKING_ENTRY_BY_INTENT.values())
)
MOUTH_MASKS_ENABLED = True
TRANSITION_HOLD_LABELS = {
    _SPEAKING_TRIGGER_LABEL,
    _CLOSED_EYE_SPEAKING_TRIGGER_LABEL,
    *_THINKING_ENTRY_LABELS,
    *_EMOTION_SPEAKING_ENTRY_BY_INTENT.values(),
}
POST_SPEECH_HOLD_SEC = 1.0
