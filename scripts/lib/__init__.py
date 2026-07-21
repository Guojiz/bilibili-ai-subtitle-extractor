"""Subtitle recipe library — platform-agnostic pipeline + adapters."""

from .detect import detect_adapter
from .models import Cue, ExtractResult, TrackInfo

__all__ = ["Cue", "ExtractResult", "TrackInfo", "detect_adapter"]
