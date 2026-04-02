"""
bots/shorts/motion_engine.py
Motion pattern engine for video clips.

Applies one of 7 motion patterns to still images using FFmpeg.
Ensures no 2 consecutive clips use the same pattern.

Patterns:
  1. ken_burns_in   — slow zoom in
  2. ken_burns_out  — slow zoom out
  3. pan_left       — pan from right to left
  4. pan_right      — pan from left to right
  5. parallax       — layered depth effect (approximated)
  6. rotate_slow    — very slow rotation
  7. glitch_reveal  — glitch-style reveal
"""
import logging
import os
import random
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PATTERNS = [
    'ken_burns_in',
    'ken_burns_out',
    'pan_left',
    'pan_right',
    'parallax',
    'rotate_slow',
    'glitch_reveal',
]

# FFmpeg filter_complex expressions for each pattern
# Input: scale to 1120x1990 (slightly larger than 1080x1920 for motion room)
PATTERN_FILTERS = {
    'ken_burns_in': (
        "scale=1120:1990,"
        "zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        ":d={dur_frames}:s=1080x1920:fps=30"
    ),
    'ken_burns_out': (
        "scale=1120:1990,"
        "zoompan=z='if(lte(zoom,1.0),1.08,max(zoom-0.0008,1.0))'"
        ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        ":d={dur_frames}:s=1080x1920:fps=30"
    ),
    'pan_left': (
        "scale=1200:1920,"
        "crop=1080:1920:'min(iw-ow, (iw-ow)*t/{duration})':0"
    ),
    'pan_right': (
        "scale=1200:1920,"
        "crop=1080:1920:'(iw-ow)*(1-t/{duration})':0"
    ),
    'parallax': (
        # Approximate parallax: zoom + horizontal pan
        "scale=1200:1990,"
        "zoompan=z='1.05':x='iw/2-(iw/zoom/2)+50*sin(2*PI*t/{duration})'"
        ":y='ih/2-(ih/zoom/2)':d={dur_frames}:s=1080x1920:fps=30"
    ),
    'rotate_slow': (
        "scale=1200:1200,"
        "rotate='0.02*t':c=black:ow=1080:oh=1920"
    ),
    'glitch_reveal': (
        # Fade in with slight chromatic aberration approximation
        "scale=1080:1920,"
        "fade=t=in:st=0:d=0.3,"
        "hue=h='if(lt(t,0.3),10*sin(30*t),0)'"
    ),
}


class MotionEngine:
    """
    Applies motion patterns to still images.
    Auto-selects patterns to avoid repeating the last 2 used.
    """

    def __init__(self):
        self._recent: list[str] = []  # last patterns used (max 2)
        self._ffmpeg = os.environ.get('FFMPEG_PATH', 'ffmpeg')

    def apply(self, image_path: str, duration: float, output_path: Optional[str] = None) -> str:
        """
        Apply a motion pattern to a still image.

        Args:
            image_path: Path to input image (PNG/JPG, 1080x1920 recommended)
            duration: Duration of output video in seconds
            output_path: Output MP4 path. If None, creates temp file.

        Returns: Path to motion-applied video clip (MP4)
        """
        if output_path is None:
            # Create a temp file that persists (caller is responsible for cleanup)
            tmp = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            output_path = tmp.name
            tmp.close()

        pattern = self._next_pattern()
        success = self._ffmpeg_motion(image_path, duration, pattern, output_path)

        if not success:
            logger.warning(f'[모션] {pattern} 패턴 실패 — ken_burns_in으로 폴백')
            success = self._ffmpeg_motion(image_path, duration, 'ken_burns_in', output_path)

        if success:
            logger.info(f'[모션] 패턴 적용: {pattern} ({duration:.1f}초)')
            return output_path
        else:
            logger.error(f'[모션] 모든 패턴 실패: {image_path}')
            return ''

    def _next_pattern(self) -> str:
        """Select next pattern, avoiding last 2 used."""
        available = [p for p in PATTERNS if p not in self._recent[-2:]]
        if not available:
            available = PATTERNS
        choice = random.choice(available)
        self._recent.append(choice)
        if len(self._recent) > 4:  # Keep small buffer
            self._recent = self._recent[-4:]
        return choice

    def _ffmpeg_motion(self, image_path: str, duration: float,
                        pattern: str, output_path: str) -> bool:
        """Apply a specific motion pattern using FFmpeg."""
        dur_frames = int(duration * 30)

        vf_template = PATTERN_FILTERS.get(pattern, PATTERN_FILTERS['ken_burns_in'])
        vf = vf_template.format(
            duration=f'{duration:.3f}',
            dur_frames=dur_frames,
        )

        cmd = [
            self._ffmpeg, '-y',
            '-loop', '1',
            '-i', str(image_path),
            '-t', f'{duration:.3f}',
            '-vf', vf,
            '-c:v', 'libx264',
            '-crf', '20',
            '-preset', 'fast',
            '-pix_fmt', 'yuv420p',
            '-an',
            '-r', '30',
            str(output_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.warning(f'[모션] FFmpeg 오류 ({pattern}): {result.stderr.decode(errors="ignore")[-200:]}')
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.warning(f'[모션] 타임아웃 ({pattern})')
            return False
        except Exception as e:
            logger.warning(f'[모션] 예외 ({pattern}): {e}')
            return False

    def get_recent(self) -> list[str]:
        """Return recently used patterns."""
        return list(self._recent)


# ── Standalone test ──────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    if '--test' in sys.argv:
        engine = MotionEngine()
        print("=== Motion Engine Test ===")
        print(f"Available patterns: {PATTERNS}")
        print(f"Pattern sequence (10 picks):")
        for i in range(10):
            p = engine._next_pattern()
            print(f"  {i+1}. {p}")
        print(f"No pattern repeated consecutively: ", end='')
        recent_list = engine.get_recent()
        no_consec = all(
            recent_list[i] != recent_list[i+1]
            for i in range(len(recent_list)-1)
        )
        print("PASS" if no_consec else "FAIL")
