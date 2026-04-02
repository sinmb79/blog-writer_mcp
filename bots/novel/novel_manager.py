"""
novel_manager.py
소설 연재 파이프라인 — 연재 관리 + Telegram 명령어 처리 모듈
역할: 소설 목록 관리, 에피소드 파이프라인 실행, 스케줄 조정, Telegram 응답
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR / 'bots'))
sys.path.insert(0, str(BASE_DIR / 'bots' / 'novel'))

logger = logging.getLogger(__name__)
if not logger.handlers:
    logs_dir = BASE_DIR / 'logs'
    logs_dir.mkdir(exist_ok=True)
    handler = logging.FileHandler(logs_dir / 'novel.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)


# ─── NovelManager ────────────────────────────────────────────────────────────

class NovelManager:
    """config/novels/*.json 전체를 관리하고 파이프라인을 실행하는 클래스."""

    def __init__(self):
        self.novels_config_dir = BASE_DIR / 'config' / 'novels'
        self.novels_data_dir = BASE_DIR / 'data' / 'novels'
        self.novels_config_dir.mkdir(parents=True, exist_ok=True)
        self.novels_data_dir.mkdir(parents=True, exist_ok=True)

    # ── 소설 목록 조회 ────────────────────────────────────────────────────────

    def get_all_novels(self) -> list:
        """config/novels/*.json 전체 로드"""
        novels = []
        for path in sorted(self.novels_config_dir.glob('*.json')):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                novels.append(data)
            except Exception as e:
                logger.error(f"소설 설정 로드 실패 ({path.name}): {e}")
        return novels

    def get_active_novels(self) -> list:
        """status == 'active' 인 소설만 반환"""
        return [n for n in self.get_all_novels() if n.get('status') == 'active']

    def get_due_novels(self) -> list:
        """
        오늘 발행 예정인 소설 반환.
        publish_schedule 예: "매주 월/목 09:00"
        """
        today_weekday = datetime.now().weekday()  # 0=월, 1=화, ..., 6=일
        _KO_DAY_MAP = {
            '월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6
        }

        due = []
        for novel in self.get_active_novels():
            schedule = novel.get('publish_schedule', '')
            try:
                # "매주 월/목 09:00" 형식 파싱
                parts = schedule.replace('매주 ', '').split(' ')
                days_part = parts[0] if parts else ''
                days = [d.strip() for d in days_part.split('/')]
                for day in days:
                    if _KO_DAY_MAP.get(day) == today_weekday:
                        due.append(novel)
                        break
            except Exception as e:
                logger.warning(f"스케줄 파싱 실패 ({novel.get('novel_id')}): {e}")
        return due

    # ── 파이프라인 실행 ───────────────────────────────────────────────────────

    def run_episode_pipeline(self, novel_id: str,
                              telegram_notify: bool = True) -> bool:
        """
        완전한 에피소드 파이프라인:
        1. NovelWriter.generate_episode()
        2. NovelBlogConverter.convert()
        3. NovelShortsConverter.generate()
        4. publisher_bot으로 블로그 발행
        5. 성공 시 Telegram 알림
        반환: 성공 여부
        """
        logger.info(f"[{novel_id}] 에피소드 파이프라인 시작")

        # 소설 설정 로드
        config_path = self.novels_config_dir / f'{novel_id}.json'
        if not config_path.exists():
            logger.error(f"소설 설정 없음: {config_path}")
            return False

        try:
            novel_config = json.loads(config_path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.error(f"소설 설정 로드 실패: {e}")
            return False

        # 데이터 디렉터리 생성
        self.create_novel_dirs(novel_id)

        # ── Step 1: 에피소드 생성 ─────────────────────────────────────────────
        episode = None
        try:
            from novel_writer import NovelWriter
            writer = NovelWriter(novel_id)
            episode = writer.generate_episode()
            if not episode:
                logger.error(f"[{novel_id}] 에피소드 생성 실패")
                return False
            logger.info(f"[{novel_id}] 에피소드 {episode['episode_num']} 생성 완료")
        except Exception as e:
            logger.error(f"[{novel_id}] Step 1 (에피소드 생성) 실패: {e}")
            return False

        # ── Step 2: 블로그 HTML 변환 ──────────────────────────────────────────
        html = ''
        try:
            from novel_blog_converter import convert as blog_convert
            html = blog_convert(episode, novel_config, save_file=True)
            logger.info(f"[{novel_id}] 블로그 HTML 변환 완료")
        except Exception as e:
            logger.error(f"[{novel_id}] Step 2 (블로그 변환) 실패: {e}")

        # ── Step 3: 쇼츠 영상 생성 ───────────────────────────────────────────
        shorts_path = ''
        try:
            from novel_shorts_converter import NovelShortsConverter
            converter = NovelShortsConverter()
            shorts_path = converter.generate(episode, novel_config)
            if shorts_path:
                logger.info(f"[{novel_id}] 쇼츠 생성 완료: {shorts_path}")
            else:
                logger.warning(f"[{novel_id}] 쇼츠 생성 실패 (계속 진행)")
        except Exception as e:
            logger.error(f"[{novel_id}] Step 3 (쇼츠 생성) 실패: {e}")

        # ── Step 4: 블로그 발행 ───────────────────────────────────────────────
        publish_ok = False
        if html:
            try:
                publish_ok = self._publish_episode(episode, novel_config, html)
                if publish_ok:
                    logger.info(f"[{novel_id}] 블로그 발행 완료")
                else:
                    logger.warning(f"[{novel_id}] 블로그 발행 실패")
            except Exception as e:
                logger.error(f"[{novel_id}] Step 4 (발행) 실패: {e}")

        # ── Step 5: Telegram 알림 ─────────────────────────────────────────────
        if telegram_notify:
            try:
                ep_num = episode.get('episode_num', 0)
                title = episode.get('title', '')
                msg = (
                    f"소설 연재 완료!\n"
                    f"제목: {novel_config.get('title_ko', novel_id)}\n"
                    f"에피소드: {ep_num}화 — {title}\n"
                    f"블로그: {'발행 완료' if publish_ok else '발행 실패'}\n"
                    f"쇼츠: {'생성 완료' if shorts_path else '생성 실패'}"
                )
                self._send_telegram(msg)
            except Exception as e:
                logger.warning(f"Telegram 알림 실패: {e}")

        success = episode is not None
        logger.info(f"[{novel_id}] 파이프라인 완료 (성공={success})")
        return success

    # ── 소설 상태 조회 ────────────────────────────────────────────────────────

    def get_novel_status(self, novel_id: str) -> dict:
        """소설 현황 반환 (에피소드 수, 마지막 발행일, 다음 예정일 등)"""
        config_path = self.novels_config_dir / f'{novel_id}.json'
        if not config_path.exists():
            return {}

        try:
            config = json.loads(config_path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.error(f"소설 설정 로드 실패: {e}")
            return {}

        episodes_dir = self.novels_data_dir / novel_id / 'episodes'
        ep_files = list(episodes_dir.glob('ep*.json')) if episodes_dir.exists() else []
        # 요약/블로그 파일 제외 (ep001.json 만 카운트)
        ep_files = [
            f for f in ep_files
            if '_summary' not in f.name and '_blog' not in f.name
        ]

        last_ep_date = ''
        if config.get('episode_log'):
            last_log = config['episode_log'][-1]
            last_ep_date = last_log.get('generated_at', '')[:10]

        return {
            'novel_id': novel_id,
            'title_ko': config.get('title_ko', ''),
            'status': config.get('status', 'unknown'),
            'current_episode': config.get('current_episode', 0),
            'episode_count_target': config.get('episode_count_target', 0),
            'episode_files': len(ep_files),
            'last_published': last_ep_date,
            'publish_schedule': config.get('publish_schedule', ''),
            'genre': config.get('genre', ''),
        }

    def list_novels_text(self) -> str:
        """Telegram용 소설 목록 텍스트 반환"""
        novels = self.get_all_novels()
        if not novels:
            return '등록된 소설이 없습니다.'

        lines = ['소설 목록:\n']
        for n in novels:
            status_label = '연재중' if n.get('status') == 'active' else '중단'
            lines.append(
                f"[{status_label}] {n.get('title_ko', n.get('novel_id', ''))}\n"
                f"  장르: {n.get('genre', '')} | "
                f"{n.get('current_episode', 0)}/{n.get('episode_count_target', 0)}화 | "
                f"{n.get('publish_schedule', '')}\n"
            )
        return '\n'.join(lines)

    # ── 디렉터리 생성 ─────────────────────────────────────────────────────────

    def create_novel_dirs(self, novel_id: str):
        """data/novels/{novel_id}/episodes/, shorts/, images/ 폴더 생성"""
        base = self.novels_data_dir / novel_id
        for sub in ['episodes', 'shorts', 'images']:
            (base / sub).mkdir(parents=True, exist_ok=True)
        logger.info(f"[{novel_id}] 데이터 디렉터리 생성: {base}")

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _publish_episode(self, episode: dict, novel_config: dict,
                          html: str) -> bool:
        """publisher_bot을 통해 블로그 발행"""
        try:
            import publisher_bot
            novel_id = novel_config.get('novel_id', '')
            ep_num = episode.get('episode_num', 0)
            title_ko = novel_config.get('title_ko', '')

            article = {
                'title': f"{title_ko} {ep_num}화 — {episode.get('title', '')}",
                'body': html,
                '_body_is_html': True,
                '_html_content': html,
                'corner': '연재소설',
                'slug': f"{novel_id}-ep{ep_num:03d}",
                'labels': ['연재소설', title_ko, f'에피소드{ep_num}'],
            }
            return publisher_bot.publish(article)
        except ImportError:
            logger.warning("publisher_bot 없음 — 발행 건너뜀")
            return False
        except Exception as e:
            logger.error(f"발행 실패: {e}")
            return False

    def _send_telegram(self, message: str):
        """Telegram 메시지 전송"""
        try:
            import telegram_bot
            telegram_bot.send_message(message)
        except ImportError:
            logger.warning("telegram_bot 없음 — 알림 건너뜀")
        except Exception as e:
            logger.warning(f"Telegram 전송 실패: {e}")

    def _update_novel_status(self, novel_id: str, status: str) -> bool:
        """소설 status 필드 업데이트 (active / paused)"""
        config_path = self.novels_config_dir / f'{novel_id}.json'
        if not config_path.exists():
            return False
        try:
            config = json.loads(config_path.read_text(encoding='utf-8'))
            config['status'] = status
            config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            logger.info(f"[{novel_id}] status 변경: {status}")
            return True
        except Exception as e:
            logger.error(f"소설 status 업데이트 실패: {e}")
            return False

    def _find_novel_by_title(self, title_query: str) -> str:
        """소설 제목(한국어 or 영어) 또는 novel_id로 검색 — novel_id 반환"""
        title_query = title_query.strip()
        for novel in self.get_all_novels():
            if (title_query in novel.get('title_ko', '')
                    or title_query in novel.get('title', '')
                    or title_query == novel.get('novel_id', '')):
                return novel.get('novel_id', '')
        return ''

    def run_all(self) -> list:
        """오늘 발행 예정인 모든 활성 소설 파이프라인 실행 (스케줄러용)"""
        results = []
        for novel in self.get_due_novels():
            novel_id = novel.get('novel_id', '')
            ok = self.run_episode_pipeline(novel_id, telegram_notify=True)
            results.append({'novel_id': novel_id, 'success': ok})
        return results


# ─── Telegram 명령 처리 함수 (scheduler.py에서 호출) ─────────────────────────

def handle_novel_command(text: str) -> str:
    """
    Telegram 소설 명령어 처리.

    지원 명령:
      "소설 새로 만들기"
      "소설 목록"
      "소설 {제목} 다음 에피소드"
      "소설 {제목} 현황"
      "소설 {제목} 중단"
      "소설 {제목} 재개"

    반환: 응답 문자열
    """
    manager = NovelManager()
    text = text.strip()

    # ── "소설 목록" ───────────────────────────────────────────────────────────
    if text in ('소설 목록', '소설목록'):
        return manager.list_novels_text()

    # ── "소설 새로 만들기" ────────────────────────────────────────────────────
    if '새로 만들기' in text or '새로만들기' in text:
        return (
            '새 소설 설정 방법:\n\n'
            '1. config/novels/ 폴더에 {novel_id}.json 파일 생성\n'
            '2. 필수 필드: novel_id, title, title_ko, genre,\n'
            '   setting, characters, base_story, publish_schedule\n'
            '3. status: "active" 로 설정하면 자동 연재 시작\n\n'
            '예시: config/novels/shadow-protocol.json 참고'
        )

    # ── "소설 {제목} 다음 에피소드" ───────────────────────────────────────────
    if '다음 에피소드' in text:
        title_query = (text.replace('소설', '', 1)
                           .replace('다음 에피소드', '')
                           .strip())
        if not title_query:
            return '소설 제목을 입력해 주세요.\n예: 소설 그림자 프로토콜 다음 에피소드'

        novel_id = manager._find_novel_by_title(title_query)
        if not novel_id:
            return (
                f'"{title_query}" 소설을 찾을 수 없습니다.\n'
                '소설 목록을 확인해 주세요.'
            )

        status_info = manager.get_novel_status(novel_id)
        if status_info.get('status') != 'active':
            return f'"{title_query}" 소설은 현재 연재 중단 상태입니다.'

        try:
            ok = manager.run_episode_pipeline(novel_id, telegram_notify=False)
            if ok:
                updated = manager.get_novel_status(novel_id)
                ep = updated.get('current_episode', 0)
                return (
                    f"에피소드 {ep}화 생성 및 발행 완료!\n"
                    f"소설: {updated.get('title_ko', novel_id)}"
                )
            else:
                return '에피소드 생성 실패. 로그를 확인해 주세요.'
        except Exception as e:
            logger.error(f"에피소드 파이프라인 오류: {e}")
            return f'오류 발생: {e}'

    # ── "소설 {제목} 현황" ────────────────────────────────────────────────────
    if '현황' in text:
        title_query = text.replace('소설', '', 1).replace('현황', '').strip()
        if not title_query:
            return '소설 제목을 입력해 주세요.\n예: 소설 그림자 프로토콜 현황'

        novel_id = manager._find_novel_by_title(title_query)
        if not novel_id:
            return f'"{title_query}" 소설을 찾을 수 없습니다.'

        s = manager.get_novel_status(novel_id)
        if not s:
            return f'"{title_query}" 현황을 불러올 수 없습니다.'

        return (
            f"소설 현황: {s.get('title_ko', novel_id)}\n\n"
            f"상태: {s.get('status', '')}\n"
            f"현재 에피소드: {s.get('current_episode', 0)}화 / "
            f"목표 {s.get('episode_count_target', 0)}화\n"
            f"마지막 발행: {s.get('last_published', '없음')}\n"
            f"연재 일정: {s.get('publish_schedule', '')}\n"
            f"장르: {s.get('genre', '')}"
        )

    # ── "소설 {제목} 중단" ────────────────────────────────────────────────────
    if '중단' in text:
        title_query = text.replace('소설', '', 1).replace('중단', '').strip()
        if not title_query:
            return '소설 제목을 입력해 주세요.\n예: 소설 그림자 프로토콜 중단'

        novel_id = manager._find_novel_by_title(title_query)
        if not novel_id:
            return f'"{title_query}" 소설을 찾을 수 없습니다.'

        ok = manager._update_novel_status(novel_id, 'paused')
        if ok:
            try:
                config = json.loads(
                    (manager.novels_config_dir / f'{novel_id}.json')
                    .read_text(encoding='utf-8')
                )
                return f'"{config.get("title_ko", novel_id)}" 연재를 일시 중단했습니다.'
            except Exception:
                return '중단 처리 완료.'
        else:
            return '중단 처리 실패. 로그를 확인해 주세요.'

    # ── "소설 {제목} 재개" ────────────────────────────────────────────────────
    if '재개' in text:
        title_query = text.replace('소설', '', 1).replace('재개', '').strip()
        if not title_query:
            return '소설 제목을 입력해 주세요.\n예: 소설 그림자 프로토콜 재개'

        novel_id = manager._find_novel_by_title(title_query)
        if not novel_id:
            return f'"{title_query}" 소설을 찾을 수 없습니다.'

        ok = manager._update_novel_status(novel_id, 'active')
        if ok:
            try:
                config = json.loads(
                    (manager.novels_config_dir / f'{novel_id}.json')
                    .read_text(encoding='utf-8')
                )
                return (
                    f'"{config.get("title_ko", novel_id)}" 연재를 재개합니다.\n'
                    f'연재 일정: {config.get("publish_schedule", "")}'
                )
            except Exception:
                return '재개 처리 완료.'
        else:
            return '재개 처리 실패. 로그를 확인해 주세요.'

    # ── 알 수 없는 명령 ───────────────────────────────────────────────────────
    return (
        '소설 명령어 목록:\n\n'
        '소설 목록\n'
        '소설 새로 만들기\n'
        '소설 {제목} 다음 에피소드\n'
        '소설 {제목} 현황\n'
        '소설 {제목} 중단\n'
        '소설 {제목} 재개'
    )


# ─── 직접 실행 테스트 ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')

    manager = NovelManager()

    print("=== 전체 소설 목록 ===")
    print(manager.list_novels_text())

    print("\n=== 활성 소설 ===")
    for n in manager.get_active_novels():
        print(f"  - {n.get('title_ko')} ({n.get('novel_id')})")

    print("\n=== 오늘 발행 예정 소설 ===")
    due = manager.get_due_novels()
    if due:
        for n in due:
            print(f"  - {n.get('title_ko')}")
    else:
        print("  (없음)")

    print("\n=== shadow-protocol 현황 ===")
    status = manager.get_novel_status('shadow-protocol')
    print(json.dumps(status, ensure_ascii=False, indent=2))

    print("\n=== Telegram 명령 테스트 ===")
    for cmd in ['소설 목록', '소설 그림자 프로토콜 현황', '소설 잘못된제목 현황']:
        print(f"\n명령: {cmd}")
        print(handle_novel_command(cmd))
