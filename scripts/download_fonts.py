"""
폰트 다운로드 스크립트
Noto Sans KR 폰트를 assets/fonts/에 다운로드.
카드 변환봇(card_converter.py)에서 사용.
실행: python scripts/download_fonts.py
"""
import os
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
FONTS_DIR = BASE_DIR / 'assets' / 'fonts'
FONTS_DIR.mkdir(parents=True, exist_ok=True)

# Google Fonts에서 직접 다운로드 (Noto Sans KR)
FONTS = {
    'NotoSansKR-Regular.ttf': (
        'https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/Korean/'
        'NotoSansCJKkr-Regular.otf'
    ),
    'NotoSansKR-Bold.ttf': (
        'https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/Korean/'
        'NotoSansCJKkr-Bold.otf'
    ),
    'NotoSansKR-Medium.ttf': (
        'https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/Korean/'
        'NotoSansCJKkr-Medium.otf'
    ),
}

# Windows에 이미 설치된 한글 폰트를 복사하는 대안
WINDOWS_FONT_CANDIDATES = [
    ('malgunbd.ttf', 'NotoSansKR-Bold.ttf'),    # 맑은고딕 Bold
    ('malgun.ttf', 'NotoSansKR-Regular.ttf'),    # 맑은고딕 Regular
    ('malgun.ttf', 'NotoSansKR-Medium.ttf'),
]


def copy_windows_fonts() -> list[str]:
    """Windows 기본 한글 폰트를 assets/fonts/에 복사"""
    import shutil
    win_fonts = Path('C:/Windows/Fonts')
    copied = []
    for src_name, dst_name in WINDOWS_FONT_CANDIDATES:
        src = win_fonts / src_name
        dst = FONTS_DIR / dst_name
        if dst.exists():
            print(f"  이미 존재: {dst_name}")
            copied.append(dst_name)
            continue
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  복사: {src_name} → {dst_name}")
            copied.append(dst_name)
        else:
            print(f"  없음: {src_name}")
    return copied


def download_from_url(url: str, dst_path: Path) -> bool:
    """URL에서 폰트 파일 다운로드"""
    try:
        print(f"  다운로드 중: {dst_path.name} ...")
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            dst_path.write_bytes(resp.read())
        print(f"  완료: {dst_path.name} ({dst_path.stat().st_size // 1024} KB)")
        return True
    except Exception as e:
        print(f"  실패: {e}")
        return False


def verify_font(font_path: Path) -> bool:
    """PIL로 폰트 로드 테스트"""
    try:
        from PIL import ImageFont
        ImageFont.truetype(str(font_path), 30)
        return True
    except Exception as e:
        print(f"  폰트 검증 실패: {e}")
        return False


def main():
    print("=== Noto Sans KR 폰트 설치 ===\n")
    print(f"대상 폴더: {FONTS_DIR}\n")

    # 1단계: Windows 기본 폰트 복사 시도 (가장 빠름)
    print("[1단계] Windows 기본 한글 폰트 복사...")
    copied = copy_windows_fonts()

    if len(copied) >= 2:
        print(f"\n[OK] Windows 폰트 복사 완료 ({len(copied)}개)")
        _verify_all()
        return

    # 2단계: GitHub에서 직접 다운로드
    print("\n[2단계] GitHub Noto Sans CJK KR 다운로드...")
    downloaded = 0
    for filename, url in FONTS.items():
        dst = FONTS_DIR / filename
        if dst.exists() and dst.stat().st_size > 1000:
            print(f"  이미 존재: {filename}")
            downloaded += 1
            continue
        if download_from_url(url, dst):
            downloaded += 1

    if downloaded > 0:
        print(f"\n✅ 다운로드 완료 ({downloaded}개)")
        _verify_all()
    else:
        print("\n❌ 폰트 설치 실패. 수동 설치 방법:")
        print("  1. https://fonts.google.com/noto/specimen/Noto+Sans+KR 에서 다운로드")
        print(f"  2. TTF 파일들을 {FONTS_DIR} 에 복사")
        print("  3. NotoSansKR-Regular.ttf, NotoSansKR-Bold.ttf 로 이름 변경")
        sys.exit(1)


def _verify_all():
    print("\n[검증] 폰트 로드 테스트...")
    ok = True
    for f in FONTS_DIR.glob('*.ttf'):
        if verify_font(f):
            print(f"  ✅ {f.name}")
        else:
            print(f"  ❌ {f.name}")
            ok = False
    if ok:
        print("\n카드 변환봇 준비 완료!")
    else:
        print("\n일부 폰트 오류. card_converter.py는 대체 폰트로 동작합니다.")


if __name__ == '__main__':
    main()
