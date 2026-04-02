"""
bots/shorts/watermark_remover.py
역할: SoraWatermarkCleaner 래퍼 — Sora 2 영상 워터마크 자동 제거

AMD / CPU 환경: LAMA 모드 사용 (NVIDIA CUDA 없이 동작)
NVIDIA GPU 환경: E2FGVI_HQ 모드 가능 (고품질, 시간적 일관성)

설치:
  cd D:/workspace
  git clone https://github.com/linkedlist771/SoraWatermarkCleaner.git
  cd SoraWatermarkCleaner && pip install uv && uv sync

환경변수:
  SORAWM_PATH=D:/workspace/SoraWatermarkCleaner   # 설치 경로
  SORAWM_MODEL=lama                                # lama | e2fgvi_hq
"""
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent

# ─── 설정 로드 ────────────────────────────────────────────────

def _get_sorawm_path() -> Optional[Path]:
    """SoraWatermarkCleaner 설치 경로 반환."""
    env_path = os.environ.get('SORAWM_PATH', '')
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    # 기본 탐색 위치
    candidates = [
        BASE_DIR.parent / 'SoraWatermarkCleaner',
        Path('D:/workspace/SoraWatermarkCleaner'),
        Path('C:/workspace/SoraWatermarkCleaner'),
    ]
    for c in candidates:
        if c.exists() and (c / 'sorawm').exists():
            return c

    return None


def _get_model() -> str:
    """사용할 모델 반환. 기본: lama (AMD/CPU 호환)."""
    return os.environ.get('SORAWM_MODEL', 'lama').lower()


def is_available() -> bool:
    """SoraWatermarkCleaner 사용 가능 여부 확인."""
    return _get_sorawm_path() is not None


# ─── 워터마크 제거 ────────────────────────────────────────────

def remove_watermark(
    input_path: Path,
    output_path: Optional[Path] = None,
    model: Optional[str] = None,
    overwrite: bool = False,
) -> Path:
    """
    Sora 2 영상에서 워터마크 제거.

    Args:
        input_path:  원본 Sora 2 MP4 경로
        output_path: 출력 경로 (None이면 {stem}_clean.mp4로 자동 결정)
        model:       'lama' 또는 'e2fgvi_hq' (None이면 환경변수/기본값 사용)
        overwrite:   이미 처리된 파일 강제 재처리

    Returns:
        처리 완료된 영상 경로

    Raises:
        RuntimeError — SoraWatermarkCleaner 미설치 또는 처리 실패
    """
    sorawm_path = _get_sorawm_path()
    if sorawm_path is None:
        raise RuntimeError(
            'SoraWatermarkCleaner를 찾을 수 없습니다.\n'
            '설치: git clone https://github.com/linkedlist771/SoraWatermarkCleaner.git\n'
            '환경변수: SORAWM_PATH=D:/workspace/SoraWatermarkCleaner'
        )

    if not input_path.exists():
        raise FileNotFoundError(f'입력 파일 없음: {input_path}')

    # 출력 경로 결정
    if output_path is None:
        output_path = input_path.parent / f'{input_path.stem}_clean{input_path.suffix}'

    # 이미 처리된 파일 재사용
    if output_path.exists() and not overwrite:
        logger.info(f'이미 처리된 파일 재사용: {output_path.name}')
        return output_path

    used_model = model or _get_model()
    logger.info(f'워터마크 제거 시작: {input_path.name} (모델: {used_model})')

    # SoraWatermarkCleaner 자체 .venv Python 사용 (의존성 분리)
    sorawm_python = sorawm_path / '.venv' / 'Scripts' / 'python.exe'
    if not sorawm_python.exists():
        sorawm_python = sorawm_path / '.venv' / 'bin' / 'python'
    if not sorawm_python.exists():
        raise RuntimeError(
            f'SoraWatermarkCleaner venv Python을 찾을 수 없습니다: {sorawm_path / ".venv"}\n'
            f'uv sync 실행 필요: cd {sorawm_path} && uv sync'
        )

    # 인라인 Python 스크립트로 실행
    run_script = (
        f'from pathlib import Path\n'
        f'from sorawm.core import SoraWM\n'
        f'from sorawm.schemas import CleanerType\n'
        f'ct = CleanerType.E2FGVI_HQ if "{used_model}" == "e2fgvi_hq" else CleanerType.LAMA\n'
        f'SoraWM(cleaner_type=ct).run(Path(r"{input_path}"), Path(r"{output_path}"))\n'
    )
    try:
        result = subprocess.run(
            [str(sorawm_python), '-c', run_script],
            cwd=str(sorawm_path),
            capture_output=True,
            timeout=1800,  # 30분 타임아웃 (긴 영상 처리 고려)
        )
        if result.returncode != 0:
            err_msg = result.stderr.decode(errors='ignore')[-500:]
            # 출력 파일이 부분적으로 생성됐으면 삭제
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            raise RuntimeError(f'sorawm 처리 실패 (rc={result.returncode}):\n{err_msg}')
    except subprocess.TimeoutExpired:
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        raise RuntimeError('워터마크 제거 타임아웃 (30분 초과)')

    if not output_path.exists():
        raise RuntimeError(f'처리 후 출력 파일 없음: {output_path}')

    in_mb = input_path.stat().st_size / (1024 * 1024)
    out_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f'워터마크 제거 완료: {output_path.name} ({in_mb:.1f}MB → {out_mb:.1f}MB)')
    return output_path


def remove_watermark_batch(
    input_paths: list[Path],
    output_dir: Optional[Path] = None,
    model: Optional[str] = None,
    overwrite: bool = False,
) -> list[tuple[Path, bool, str]]:
    """
    여러 영상 일괄 워터마크 제거.

    Returns:
        [(output_path, success, error_msg), ...]
    """
    results = []
    for src in input_paths:
        out = None
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            out = output_dir / f'{src.stem}_clean{src.suffix}'
        try:
            cleaned = remove_watermark(src, out, model, overwrite)
            results.append((cleaned, True, ''))
        except Exception as e:
            logger.error(f'배치 처리 실패 [{src.name}]: {e}')
            results.append((src, False, str(e)))
    return results


def remove_if_sora(
    video_path: Path,
    model: Optional[str] = None,
) -> Path:
    """
    SoraWatermarkCleaner가 설치돼 있으면 워터마크 제거, 없으면 원본 그대로 반환.
    파이프라인 선택적 통합용 (설치 안 해도 동작).
    """
    if not is_available():
        logger.debug('SoraWatermarkCleaner 미설치 — 워터마크 제거 건너뜀')
        return video_path

    try:
        return remove_watermark(video_path, model=model)
    except Exception as e:
        logger.warning(f'워터마크 제거 실패, 원본 사용: {e}')
        return video_path
