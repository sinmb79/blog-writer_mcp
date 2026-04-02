"""
scripts/remove_watermark.py
역할: Sora 2 영상 워터마크 독립 실행 제거 스크립트 (Method A)

사용법:
  python scripts/remove_watermark.py video.mp4
  python scripts/remove_watermark.py video.mp4 -o cleaned.mp4
  python scripts/remove_watermark.py input_folder/ -o output_folder/
  python scripts/remove_watermark.py video.mp4 --model e2fgvi_hq

AMD/CPU 환경: lama 모드 권장 (기본값)
NVIDIA GPU  : e2fgvi_hq 모드 가능 (고품질, 느림)
"""
import argparse
import sys
from pathlib import Path

# blog-writer 루트를 path에 추가
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / 'bots'))

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')


def main():
    parser = argparse.ArgumentParser(
        description='Sora 2 영상 워터마크 제거',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/remove_watermark.py video.mp4
  python scripts/remove_watermark.py video.mp4 -o cleaned.mp4
  python scripts/remove_watermark.py D:/sora_videos/ -o D:/cleaned/
  python scripts/remove_watermark.py video.mp4 --model e2fgvi_hq --overwrite

모델 선택:
  lama       빠름, CPU/AMD 호환, 기본값
  e2fgvi_hq  최고 품질, NVIDIA GPU 필요
        """,
    )
    parser.add_argument('input', help='입력 영상 파일 또는 폴더 경로')
    parser.add_argument('-o', '--output', help='출력 파일 또는 폴더 경로 (기본: 입력과 같은 위치에 _clean 추가)')
    parser.add_argument('-m', '--model', choices=['lama', 'e2fgvi_hq'], default='lama',
                        help='제거 모델 (기본: lama)')
    parser.add_argument('--overwrite', action='store_true', help='이미 처리된 파일 강제 재처리')
    args = parser.parse_args()

    from shorts.watermark_remover import remove_watermark, remove_watermark_batch, is_available

    # 설치 확인
    if not is_available():
        print('[오류] SoraWatermarkCleaner가 설치되지 않았습니다.')
        print()
        print('설치 방법:')
        print('  cd D:\\workspace')
        print('  git clone https://github.com/linkedlist771/SoraWatermarkCleaner.git')
        print('  cd SoraWatermarkCleaner')
        print('  pip install uv && uv sync')
        print()
        print('또는 .env에 SORAWM_PATH=설치경로 추가')
        sys.exit(1)

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else None

    # 폴더 배치 처리
    if input_path.is_dir():
        video_files = list(input_path.glob('*.mp4')) + list(input_path.glob('*.mov'))
        if not video_files:
            print(f'[오류] {input_path}에 mp4/mov 파일이 없습니다.')
            sys.exit(1)

        out_dir = output_path or input_path / 'cleaned'
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f'배치 처리: {len(video_files)}개 영상 → {out_dir}')
        results = remove_watermark_batch(video_files, out_dir, args.model, args.overwrite)

        ok = sum(1 for _, s, _ in results if s)
        fail = len(results) - ok
        print(f'\n완료: 성공 {ok}개 / 실패 {fail}개')
        for path, success, err in results:
            icon = '✅' if success else '❌'
            msg = f'  {icon} {path.name}'
            if not success:
                msg += f' — {err}'
            print(msg)
        sys.exit(0 if fail == 0 else 1)

    # 단일 파일 처리
    if not input_path.exists():
        print(f'[오류] 파일 없음: {input_path}')
        sys.exit(1)

    print(f'처리 중: {input_path.name} (모델: {args.model})')
    try:
        result = remove_watermark(input_path, output_path, args.model, args.overwrite)
        print(f'✅ 완료: {result}')
    except Exception as e:
        print(f'❌ 실패: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
