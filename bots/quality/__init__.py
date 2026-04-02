"""
bots/quality
Quality signal computation for shorts content.

V3.0 signals:
  - motion_variation_score
  - script_diversity_score
  - tts_cost_efficiency

V3.1+ additions:
  - semantic_visual_score
  - caption_overlap_score
  - pacing_variation_score
"""
from .micro_signals import compute_signal, SIGNALS_V1

__all__ = ['compute_signal', 'SIGNALS_V1']
