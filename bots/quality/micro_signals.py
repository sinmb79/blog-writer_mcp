"""
bots/quality/micro_signals.py
Micro-failure quality signals for shorts content.

V3.0 scope: 3 signals
  - motion_variation_score: detects repetitive motion patterns
  - script_diversity_score: detects structural overlap with recent scripts
  - tts_cost_efficiency: monitors TTS credit usage

Each signal returns a float 0.0-1.0 where:
  - 1.0 = perfect / no issue
  - 0.0 = critical problem
  - threshold = action trigger point
"""
import logging
from pathlib import Path
from typing import Callable, Any

logger = logging.getLogger(__name__)

SIGNALS_V1 = {
    'motion_variation_score': {
        'description': 'Consecutive clips using same motion pattern',
        'threshold': 0.6,
        'action': 'auto_fix',   # pick different pattern automatically
        'higher_is_better': True,
    },
    'script_diversity_score': {
        'description': 'Script structure overlap with last 7 days',
        'threshold': 0.5,
        'action': 'regenerate',  # request different structure from LLM
        'higher_is_better': True,
    },
    'tts_cost_efficiency': {
        'description': 'TTS credit usage vs monthly limit',
        'threshold': 0.8,
        'action': 'switch_engine',  # downgrade to local TTS
        'higher_is_better': False,  # lower usage = better
    },
}


def compute_signal(signal_name: str, **kwargs) -> float:
    """
    Compute a quality signal value.

    Args:
        signal_name: One of SIGNALS_V1 keys
        **kwargs: Signal-specific inputs (see individual compute functions)

    Returns: float 0.0-1.0

    Raises: ValueError if signal_name unknown
    """
    if signal_name not in SIGNALS_V1:
        raise ValueError(f'Unknown signal: {signal_name}. Available: {list(SIGNALS_V1.keys())}')

    compute_fns = {
        'motion_variation_score': _compute_motion_variation,
        'script_diversity_score': _compute_script_diversity,
        'tts_cost_efficiency': _compute_tts_cost_efficiency,
    }

    fn = compute_fns[signal_name]
    try:
        value = fn(**kwargs)
        logger.debug(f'[품질] {signal_name} = {value:.3f}')
        return value
    except Exception as e:
        logger.warning(f'[품질] 신호 계산 실패 ({signal_name}): {e}')
        return 1.0  # Neutral value on error (don't trigger action)


def check_and_act(signal_name: str, value: float) -> dict:
    """
    Check if signal value crosses threshold and return action.

    Returns: {
        'triggered': bool,
        'action': str or None,
        'value': float,
        'threshold': float,
    }
    """
    if signal_name not in SIGNALS_V1:
        return {'triggered': False, 'action': None, 'value': value, 'threshold': 0}

    config = SIGNALS_V1[signal_name]
    threshold = config['threshold']
    higher_is_better = config.get('higher_is_better', True)

    if higher_is_better:
        triggered = value < threshold
    else:
        triggered = value > threshold

    return {
        'triggered': triggered,
        'action': config['action'] if triggered else None,
        'value': value,
        'threshold': threshold,
    }


def _compute_motion_variation(clips: list, **kwargs) -> float:
    """
    Compute motion variation score.

    Args:
        clips: list of dicts with 'pattern' key, e.g. [{'pattern': 'ken_burns_in'}, ...]

    Returns: 0.0-1.0 diversity score
    """
    if not clips or len(clips) < 2:
        return 1.0

    patterns = [c.get('pattern', '') for c in clips if c.get('pattern')]
    if not patterns:
        return 1.0

    # Count consecutive same-pattern pairs
    consecutive_same = sum(
        1 for i in range(len(patterns) - 1)
        if patterns[i] == patterns[i+1]
    )

    # Unique patterns ratio
    unique_ratio = len(set(patterns)) / len(patterns)
    consecutive_penalty = consecutive_same / max(len(patterns) - 1, 1)

    score = unique_ratio * (1 - consecutive_penalty)
    return round(min(1.0, max(0.0, score)), 3)


def _compute_script_diversity(script: dict, history: list = None, **kwargs) -> float:
    """
    Compute script structure diversity vs recent history.

    Args:
        script: Current script dict with 'hook', 'body', 'closer'
        history: List of recent scripts (last 7 days), each same format

    Returns: 0.0-1.0 diversity score (1.0 = very diverse)
    """
    if not history:
        return 1.0

    # Compare script structure fingerprints
    def _fingerprint(s: dict) -> tuple:
        hook = s.get('hook', '')
        body = s.get('body', [])
        closer = s.get('closer', '')
        return (
            len(hook) // 10,  # rough length bucket
            len(body),         # number of body sentences
            hook[:5] if hook else '',   # hook start
        )

    current_fp = _fingerprint(script)

    overlaps = sum(
        1 for h in history
        if _fingerprint(h) == current_fp
    )

    overlap_rate = overlaps / len(history)
    return round(1.0 - overlap_rate, 3)


def _compute_tts_cost_efficiency(usage: float, limit: float, **kwargs) -> float:
    """
    Compute TTS cost efficiency.

    Args:
        usage: Characters used this period
        limit: Monthly/daily character limit

    Returns: ratio (usage/limit), where > threshold triggers engine switch
    """
    if limit <= 0:
        return 0.0
    return round(min(1.0, usage / limit), 3)


# ── Standalone test ──────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    if '--test' in sys.argv:
        print("=== Micro Signals Test ===")

        # Test motion variation
        test_clips = [
            {'pattern': 'ken_burns_in'},
            {'pattern': 'ken_burns_in'},  # repeat!
            {'pattern': 'pan_left'},
            {'pattern': 'pan_right'},
        ]
        mv = compute_signal('motion_variation_score', clips=test_clips)
        result = check_and_act('motion_variation_score', mv)
        print(f"motion_variation_score = {mv:.3f} (triggered: {result['triggered']}, action: {result['action']})")

        # Test script diversity
        current_script = {'hook': '이거 모르면 손해', 'body': ['첫째', '둘째', '셋째'], 'closer': '구독'}
        history = [
            {'hook': '이거 모르면 손해2', 'body': ['a', 'b', 'c'], 'closer': '팔로우'},
        ]
        sd = compute_signal('script_diversity_score', script=current_script, history=history)
        result2 = check_and_act('script_diversity_score', sd)
        print(f"script_diversity_score = {sd:.3f} (triggered: {result2['triggered']})")

        # Test TTS cost
        tce = compute_signal('tts_cost_efficiency', usage=8500, limit=10000)
        result3 = check_and_act('tts_cost_efficiency', tce)
        print(f"tts_cost_efficiency = {tce:.3f} (triggered: {result3['triggered']}, action: {result3['action']})")
