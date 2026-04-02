"""
novel_writer.py
소설 연재 파이프라인 — AI 에피소드 생성 모듈
역할: 소설 설정 + 이전 요약을 기반으로 다음 에피소드 자동 작성
출력: data/novels/{novel_id}/episodes/ep{N:03d}.json + ep{N:03d}_summary.txt
"""
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

# novel/ 폴더 기준으로 BASE_DIR 설정
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR / 'bots'))

logger = logging.getLogger(__name__)

# ─── EngineLoader / fallback ─────────────────────────────────────────────────

try:
    from engine_loader import EngineLoader as _EngineLoader
    _engine_loader_available = True
except ImportError:
    _engine_loader_available = False


def _make_fallback_writer():
    """engine_loader 없을 때 anthropic SDK 직접 사용"""
    import anthropic
    import os
    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY', ''))

    class _DirectWriter:
        def write(self, prompt: str, system: str = '') -> str:
            msg = client.messages.create(
                model='claude-opus-4-6',
                max_tokens=4000,
                system=system or '당신은 한국어 연재소설 작가입니다.',
                messages=[{'role': 'user', 'content': prompt}],
            )
            return msg.content[0].text

    return _DirectWriter()


# ─── NovelWriter ─────────────────────────────────────────────────────────────

class NovelWriter:
    """소설 설정을 읽어 다음 에피소드를 AI로 생성하고 저장하는 클래스."""

    def __init__(self, novel_id: str, engine=None):
        """
        novel_id: config/novels/{novel_id}.json 로드
        engine  : EngineLoader 인스턴스 (없으면 내부에서 생성 또는 fallback)
        """
        self.novel_id = novel_id
        self.novel_config = self._load_novel_config()

        # writer 인스턴스 결정
        if engine is not None:
            self.writer = engine.get_writer()
        elif _engine_loader_available:
            self.writer = _EngineLoader().get_writer()
        else:
            logger.warning("engine_loader 없음 — anthropic SDK fallback 사용")
            self.writer = _make_fallback_writer()

        # 데이터 디렉터리 준비
        self.episodes_dir = BASE_DIR / 'data' / 'novels' / novel_id / 'episodes'
        self.episodes_dir.mkdir(parents=True, exist_ok=True)

    # ── 공개 API ──────────────────────────────────────────────────────────────

    def generate_episode(self) -> dict:
        """
        다음 에피소드 생성.
        반환:
          novel_id, episode_num, title, body (2000-3000자),
          hook (다음 회 예고 한 줄), key_scenes (쇼츠용 핵심 장면 3개),
          summary (5줄 이내), generated_at
        """
        ep_num = self.novel_config.get('current_episode', 0) + 1
        logger.info(f"[{self.novel_id}] 에피소드 {ep_num} 생성 시작")

        try:
            prev_summaries = self._get_previous_summaries(last_n=5)
            prompt = self._build_prompt(ep_num, prev_summaries)

            system_msg = (
                '당신은 한국어 연재소설 전문 작가입니다. '
                '지시한 출력 형식을 정확히 지켜 작성하세요.'
            )
            raw = self.writer.write(prompt, system=system_msg)

            episode = self._parse_episode_response(raw)
            episode['novel_id'] = self.novel_id
            episode['episode_num'] = ep_num
            episode['generated_at'] = datetime.now(timezone.utc).isoformat()

            # 요약 생성
            episode['summary'] = self._generate_summary(episode)

            # 저장
            self._save_episode(episode)

            logger.info(f"[{self.novel_id}] 에피소드 {ep_num} 생성 완료")
            return episode

        except Exception as e:
            logger.error(f"[{self.novel_id}] 에피소드 생성 실패: {e}")
            return {}

    # ── 내부 메서드 ───────────────────────────────────────────────────────────

    def _load_novel_config(self) -> dict:
        """config/novels/{novel_id}.json 로드"""
        path = BASE_DIR / 'config' / 'novels' / f'{self.novel_id}.json'
        if not path.exists():
            logger.error(f"소설 설정 파일 없음: {path}")
            return {}
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.error(f"소설 설정 로드 실패: {e}")
            return {}

    def _build_prompt(self, ep_num: int, prev_summaries: list[str]) -> str:
        """AI에게 전달할 에피소드 작성 프롬프트 구성"""
        novel = self.novel_config
        setting = novel.get('setting', {})
        characters = novel.get('characters', [])

        # 등장인물 포맷팅
        char_lines = []
        for c in characters:
            char_lines.append(
                f"- {c['name']} ({c['role']}): {c['description']} / {c['personality']}"
            )
        char_text = '\n'.join(char_lines) if char_lines else '(없음)'

        # 이전 요약 포맷팅
        if prev_summaries:
            summaries_text = '\n'.join(
                f"[{i+1}회 전] {s}" for i, s in enumerate(reversed(prev_summaries))
            )
        else:
            summaries_text = '(첫 번째 에피소드입니다)'

        rules_text = '\n'.join(f'- {r}' for r in setting.get('rules', []))

        return f"""당신은 연재 소설 작가입니다.

[소설 정보]
제목: {novel.get('title_ko', '')} ({novel.get('title', '')})
장르: {novel.get('genre', '')}
세계관: {setting.get('world', '')}
분위기: {setting.get('atmosphere', '')}
세계 규칙:
{rules_text}

[등장인물]
{char_text}

[기본 스토리]
{novel.get('base_story', '')}

[이전 에피소드 요약 (최신순)]
{summaries_text}

[지시]
에피소드 {ep_num}을 작성하세요.
- 분량: {novel.get('episode_length', '2000-3000자')}
- 톤: {novel.get('tone', '긴장감 있는 서스펜스')}
- 에피소드 끝에 반드시 다음 회가 궁금한 훅(cliffhanger) 포함
- 아래 형식을 정확히 지켜 출력하세요 (각 구분자 뒤에 바로 내용):

---EPISODE_TITLE---
(에피소드 제목, 한 줄)
---EPISODE_BODY---
(에피소드 본문, {novel.get('episode_length', '2000-3000자')})
---EPISODE_HOOK---
(다음 회 예고 한 줄, 독자의 궁금증을 자극하는 문장)
---KEY_SCENES---
(쇼츠 영상용 핵심 장면 3개, 각각 한 줄씩. 시각적으로 묘사)
장면1: (장면 묘사)
장면2: (장면 묘사)
장면3: (장면 묘사)"""

    def _get_previous_summaries(self, last_n: int = 5) -> list[str]:
        """data/novels/{novel_id}/episodes/ep{N:03d}_summary.txt 로드 (최신 N개)"""
        current_ep = self.novel_config.get('current_episode', 0)
        summaries = []
        # 최신 에피소드부터 역순으로 탐색
        for ep in range(current_ep, max(0, current_ep - last_n), -1):
            path = self.episodes_dir / f'ep{ep:03d}_summary.txt'
            if path.exists():
                try:
                    text = path.read_text(encoding='utf-8').strip()
                    if text:
                        summaries.append(text)
                except Exception as e:
                    logger.warning(f"요약 로드 실패 ep{ep:03d}: {e}")
        return summaries  # 최신순 반환

    def _parse_episode_response(self, raw: str) -> dict:
        """
        AI 응답 파싱:
        ---EPISODE_TITLE--- / ---EPISODE_BODY--- / ---EPISODE_HOOK--- / ---KEY_SCENES---
        섹션별로 분리하여 dict 반환
        """
        sections = {}
        pattern = re.compile(
            r'---(\w+)---\s*\n(.*?)(?=---\w+---|$)',
            re.DOTALL
        )
        for key, value in pattern.findall(raw):
            sections[key.strip()] = value.strip()

        # KEY_SCENES 파싱 (장면1: ~, 장면2: ~, 장면3: ~ 형식)
        key_scenes_raw = sections.get('KEY_SCENES', '')
        key_scenes = []
        for line in key_scenes_raw.splitlines():
            line = line.strip()
            # "장면N:" 또는 "N." 또는 "- " 접두사 제거
            line = re.sub(r'^(장면\d+[:.]?\s*|\d+[.)\s]+|-\s*)', '', line).strip()
            if line:
                key_scenes.append(line)
        key_scenes = key_scenes[:3]

        # 최소 3개 채우기
        while len(key_scenes) < 3:
            key_scenes.append('')

        return {
            'title': sections.get('EPISODE_TITLE', f'에피소드'),
            'body': sections.get('EPISODE_BODY', raw),
            'hook': sections.get('EPISODE_HOOK', ''),
            'key_scenes': key_scenes,
            'summary': '',  # _generate_summary에서 채움
        }

    def _generate_summary(self, episode: dict) -> str:
        """에피소드를 5줄 이내로 요약 (다음 회 컨텍스트용)"""
        body = episode.get('body', '')
        if not body:
            return ''

        prompt = f"""다음 소설 에피소드를 5줄 이내로 간결하게 요약하세요.
다음 에피소드 작가가 스토리 흐름을 파악할 수 있도록 핵심 사건과 결말만 담으세요.

에피소드 제목: {episode.get('title', '')}
에피소드 본문:
{body[:2000]}

5줄 이내 요약:"""

        try:
            summary = self.writer.write(prompt, system='당신은 소설 편집자입니다.')
            return summary.strip()
        except Exception as e:
            logger.error(f"요약 생성 실패: {e}")
            # 폴백: 본문 앞 200자
            return body[:200] + '...'

    def _save_episode(self, episode: dict):
        """
        data/novels/{novel_id}/episodes/ep{N:03d}.json 저장
        data/novels/{novel_id}/episodes/ep{N:03d}_summary.txt 저장
        config/novels/{novel_id}.json의 current_episode + episode_log 업데이트
        """
        ep_num = episode.get('episode_num', 0)
        ep_prefix = f'ep{ep_num:03d}'

        # JSON 저장
        json_path = self.episodes_dir / f'{ep_prefix}.json'
        try:
            json_path.write_text(
                json.dumps(episode, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            logger.info(f"에피소드 저장: {json_path}")
        except Exception as e:
            logger.error(f"에피소드 JSON 저장 실패: {e}")

        # 요약 저장
        summary = episode.get('summary', '')
        if summary:
            summary_path = self.episodes_dir / f'{ep_prefix}_summary.txt'
            try:
                summary_path.write_text(summary, encoding='utf-8')
                logger.info(f"요약 저장: {summary_path}")
            except Exception as e:
                logger.error(f"요약 저장 실패: {e}")

        # 소설 설정 업데이트 (current_episode, episode_log)
        config_path = BASE_DIR / 'config' / 'novels' / f'{self.novel_id}.json'
        try:
            config = json.loads(config_path.read_text(encoding='utf-8'))
            config['current_episode'] = ep_num
            log_entry = {
                'episode_num': ep_num,
                'title': episode.get('title', ''),
                'generated_at': episode.get('generated_at', ''),
            }
            if 'episode_log' not in config:
                config['episode_log'] = []
            config['episode_log'].append(log_entry)
            config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            # 로컬 캐시도 업데이트
            self.novel_config = config
            logger.info(f"소설 설정 업데이트: current_episode={ep_num}")
        except Exception as e:
            logger.error(f"소설 설정 업데이트 실패: {e}")


# ─── 직접 실행 테스트 ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')
    writer = NovelWriter('shadow-protocol')
    ep = writer.generate_episode()
    if ep:
        print(f"생성 완료: 에피소드 {ep['episode_num']} — {ep['title']}")
        print(f"본문 길이: {len(ep['body'])}자")
        print(f"훅: {ep['hook']}")
    else:
        print("에피소드 생성 실패")
