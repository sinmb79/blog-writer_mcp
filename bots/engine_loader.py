"""
엔진 로더 (bots/engine_loader.py)
역할: config/engine.json을 읽어 현재 설정된 provider에 맞는 구현체를 반환
설계서: blog-engine-final-masterplan-v3.txt

사용:
    loader = EngineLoader()
    writer = loader.get_writer()
    result = writer.write("AI 관련 기사 써줘")
    tts = loader.get_tts()
    tts.synthesize("안녕하세요", "/tmp/out.wav")
"""
import json
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / 'config' / 'engine.json'
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_DIR / 'engine_loader.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)


# ─── 기본 추상 클래스 ──────────────────────────────────

class BaseWriter(ABC):
    @abstractmethod
    def write(self, prompt: str, system: str = '') -> str:
        """글쓰기 요청. prompt에 대한 결과 문자열 반환."""


class BaseTTS(ABC):
    @abstractmethod
    def synthesize(self, text: str, output_path: str,
                   lang: str = 'ko', speed: float = 1.05) -> bool:
        """TTS 합성. 성공 시 True 반환."""


class BaseImageGenerator(ABC):
    @abstractmethod
    def generate(self, prompt: str, output_path: str,
                 size: str = '1024x1792') -> bool:
        """이미지 생성. 성공 시 True 반환."""


# VideoEngine은 video_engine.py에 정의됨
# BaseVideoGenerator 타입 힌트 호환용
BaseVideoGenerator = object


# ─── Writer 구현체 ──────────────────────────────────────

class ClaudeWriter(BaseWriter):
    """Anthropic Claude API를 사용하는 글쓰기 엔진"""

    def __init__(self, cfg: dict):
        self.api_key = os.getenv(cfg.get('api_key_env', 'ANTHROPIC_API_KEY'), '')
        self.model = cfg.get('model', 'claude-opus-4-5')
        self.max_tokens = cfg.get('max_tokens', 4096)
        self.temperature = cfg.get('temperature', 0.7)

    def write(self, prompt: str, system: str = '') -> str:
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY 없음 — ClaudeWriter 비활성화")
            return ''
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            kwargs: dict = {
                'model': self.model,
                'max_tokens': self.max_tokens,
                'messages': [{'role': 'user', 'content': prompt}],
            }
            if system:
                kwargs['system'] = system
            message = client.messages.create(**kwargs)
            return message.content[0].text
        except Exception as e:
            logger.error(f"ClaudeWriter 오류: {e}")
            return ''


class OpenClawWriter(BaseWriter):
    """OpenClaw CLI를 subprocess로 호출하는 글쓰기 엔진 (ChatGPT Pro OAuth)"""

    # Windows에서 npm 글로벌 .cmd 스크립트 우선 사용
    _CLI = 'openclaw.cmd' if os.name == 'nt' else 'openclaw'

    def __init__(self, cfg: dict):
        self.agent_name = cfg.get('agent_name', 'blog-writer')
        self.timeout = cfg.get('timeout', 300)

    def write(self, prompt: str, system: str = '') -> str:
        try:
            message = f"{system}\n\n{prompt}".strip() if system else prompt
            cmd = [
                self._CLI, 'agent',
                '--agent', self.agent_name,
                '--message', message,
                '--json',
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.timeout,
                shell=False,
            )
            stderr_str = result.stderr.decode('utf-8', errors='replace').strip()
            if result.returncode != 0:
                logger.error(f"OpenClawWriter returncode={result.returncode} stderr={stderr_str[:300]}")
                return ''
            # stdout이 비어있는 경우 — openclaw가 stderr에만 출력하거나 인증 실패
            if not result.stdout:
                logger.error(f"OpenClawWriter stdout 비어있음 (returncode=0) stderr={stderr_str[:300]}")
                return ''
            stdout = result.stdout.decode('utf-8', errors='replace').strip()
            if not stdout:
                logger.error("OpenClawWriter stdout 디코딩 후 비어있음")
                return ''
            # 1) JSON 응답 시도 — JSON 블록 추출
            json_candidate = stdout
            if not stdout.startswith('{'):
                import re
                m = re.search(r'\{[\s\S]*\}', stdout)
                json_candidate = m.group(0) if m else ''
            if json_candidate:
                try:
                    data = json.loads(json_candidate)
                    payloads = data.get('result', {}).get('payloads', [])
                    if payloads:
                        return payloads[0].get('text', '') or stdout
                except json.JSONDecodeError:
                    pass
            # 2) JSON 파싱 실패 또는 payloads 없음 → plain text 그대로 반환
            logger.info(f"OpenClawWriter plain text 응답 ({len(stdout)}자)")
            return stdout
        except subprocess.TimeoutExpired:
            logger.error(f"OpenClawWriter 타임아웃 ({self.timeout}초)")
            return ''
        except FileNotFoundError:
            logger.warning("openclaw CLI 없음 — OpenClawWriter 비활성화")
            return ''
        except Exception as e:
            logger.error(f"OpenClawWriter 오류: {e}")
            return ''


class GeminiWriter(BaseWriter):
    """Google Gemini API를 사용하는 글쓰기 엔진"""

    def __init__(self, cfg: dict):
        self.api_key = os.getenv(cfg.get('api_key_env', 'GEMINI_API_KEY'), '')
        self.model = cfg.get('model', 'gemini-2.0-flash')
        self.max_tokens = cfg.get('max_tokens', 4096)
        self.temperature = cfg.get('temperature', 0.7)

    def write(self, prompt: str, system: str = '') -> str:
        if not self.api_key:
            logger.warning("GEMINI_API_KEY 없음 — GeminiWriter 비활성화")
            return ''
        try:
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                model_name=self.model,
                generation_config={
                    'max_output_tokens': self.max_tokens,
                    'temperature': self.temperature,
                },
                system_instruction=system if system else None,
            )
            response = model.generate_content(prompt)
            return response.text
        except ImportError:
            logger.warning("google-generativeai 미설치 — GeminiWriter 비활성화")
            return ''
        except Exception as e:
            logger.error(f"GeminiWriter 오류: {e}")
            return ''


class ClaudeWebWriter(BaseWriter):
    """Playwright Chromium에 세션 쿠키를 주입해 claude.ai를 자동화하는 Writer

    Chrome을 닫을 필요 없음 — Playwright 자체 Chromium을 별도로 실행.
    필요 환경변수:
        CLAUDE_WEB_COOKIE  — __Secure-next-auth.session-token 값
    """

    def __init__(self, cfg: dict):
        self.cookie = os.getenv(cfg.get('cookie_env', 'CLAUDE_WEB_COOKIE'), '')
        self.timeout_ms = cfg.get('timeout', 180) * 1000

    def write(self, prompt: str, system: str = '') -> str:
        # claude.ai는 Cloudflare Turnstile로 헤드리스 브라우저를 차단함
        # 쿠키 세션 만료 여부와 무관하게 자동화 불가 → 비활성화
        logger.warning("ClaudeWebWriter: Cloudflare 차단으로 비활성화 (수동 사용 권장)")
        return ''
        if not self.cookie:
            logger.warning("CLAUDE_WEB_COOKIE 없음 — ClaudeWebWriter 비활성화")
            return ''
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("playwright 미설치 — ClaudeWebWriter 비활성화")
            return ''
        token = self.cookie.strip()
        message = f"{system}\n\n{prompt}".strip() if system else prompt
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled'],
                )
                ctx = browser.new_context(
                    user_agent=(
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/131.0.0.0 Safari/537.36'
                    ),
                )
                # 세션 쿠키 주입
                ctx.add_cookies([{
                    'name': '__Secure-next-auth.session-token',
                    'value': token,
                    'domain': 'claude.ai',
                    'path': '/',
                    'secure': True,
                    'httpOnly': True,
                }])
                page = ctx.new_page()
                try:
                    from playwright_stealth import stealth_sync
                    stealth_sync(page)
                except ImportError:
                    pass
                page.goto('https://claude.ai/new', wait_until='domcontentloaded', timeout=60000)
                page.wait_for_timeout(3000)
                # 입력창 대기
                editor = page.locator('[contenteditable="true"]').first
                editor.wait_for(timeout=30000)
                editor.click()
                page.keyboard.type(message, delay=30)
                page.keyboard.press('Enter')
                # 스트리밍 완료 대기 — 전송 버튼 재활성화
                page.wait_for_selector(
                    'button[aria-label="Send message"]:not([disabled])',
                    timeout=self.timeout_ms,
                )
                # 응답 텍스트 추출
                blocks = page.locator('.font-claude-message')
                text = blocks.last.inner_text() if blocks.count() else ''
                browser.close()
                return text.strip()
        except Exception as e:
            logger.error(f"ClaudeWebWriter 오류: {e}")
            return ''


class GeminiWebWriter(BaseWriter):
    """gemini.google.com 웹 세션 쿠키를 사용하는 비공식 Writer (gemini-webapi)

    필요 환경변수:
        GEMINI_WEB_1PSID    — 브라우저 DevTools > Application > Cookies >
                              google.com 에서 __Secure-1PSID 값
        GEMINI_WEB_1PSIDTS  — 같은 위치에서 __Secure-1PSIDTS 값
    """

    def __init__(self, cfg: dict):
        self.psid = os.getenv(cfg.get('psid_env', 'GEMINI_WEB_1PSID'), '')
        self.psidts = os.getenv(cfg.get('psidts_env', 'GEMINI_WEB_1PSIDTS'), '')

    def write(self, prompt: str, system: str = '') -> str:
        if not self.psid or not self.psidts:
            logger.warning("GEMINI_WEB_1PSID / GEMINI_WEB_1PSIDTS 없음 — GeminiWebWriter 비활성화")
            return ''
        try:
            import asyncio
            from gemini_webapi import GeminiClient

            async def _run():
                client = GeminiClient(secure_1psid=self.psid, secure_1psidts=self.psidts)
                await client.init(timeout=30, auto_close=False, close_delay=300)
                message = f"{system}\n\n{prompt}".strip() if system else prompt
                resp = await client.generate_content(message)
                return resp.text

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, _run())
                        return future.result(timeout=120)
                else:
                    return loop.run_until_complete(_run())
            except RuntimeError:
                return asyncio.run(_run())
        except Exception as e:
            logger.error(f"GeminiWebWriter 오류: {e}")
            return ''


# ─── TTS 구현체 ─────────────────────────────────────────

class GoogleCloudTTS(BaseTTS):
    """Google Cloud TTS REST API (API Key 방식)"""

    def __init__(self, cfg: dict):
        self.api_key = os.getenv(cfg.get('api_key_env', 'GOOGLE_TTS_API_KEY'), '')
        self.voice = cfg.get('voice', 'ko-KR-Wavenet-A')
        self.default_speed = cfg.get('speaking_rate', 1.05)
        self.pitch = cfg.get('pitch', 0)

    def synthesize(self, text: str, output_path: str,
                   lang: str = 'ko', speed: float = 0.0) -> bool:
        if not self.api_key:
            logger.warning("GOOGLE_TTS_API_KEY 없음 — GoogleCloudTTS 비활성화")
            return False
        import base64
        try:
            import requests as req
            speaking_rate = speed if speed > 0 else self.default_speed
            voice_name = self.voice if lang == 'ko' else 'en-US-Wavenet-D'
            language_code = 'ko-KR' if lang == 'ko' else 'en-US'
            url = (
                f'https://texttospeech.googleapis.com/v1/text:synthesize'
                f'?key={self.api_key}'
            )
            payload = {
                'input': {'text': text},
                'voice': {'languageCode': language_code, 'name': voice_name},
                'audioConfig': {
                    'audioEncoding': 'LINEAR16',
                    'speakingRate': speaking_rate,
                    'pitch': self.pitch,
                },
            }
            resp = req.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            audio_b64 = resp.json().get('audioContent', '')
            if audio_b64:
                Path(output_path).write_bytes(base64.b64decode(audio_b64))
                return True
        except Exception as e:
            logger.warning(f"GoogleCloudTTS 실패: {e}")
        return False


class OpenAITTS(BaseTTS):
    """OpenAI TTS API (tts-1-hd)"""

    def __init__(self, cfg: dict):
        self.api_key = os.getenv(cfg.get('api_key_env', 'OPENAI_API_KEY'), '')
        self.model = cfg.get('model', 'tts-1-hd')
        self.voice = cfg.get('voice', 'alloy')
        self.default_speed = cfg.get('speed', 1.0)

    def synthesize(self, text: str, output_path: str,
                   lang: str = 'ko', speed: float = 0.0) -> bool:
        if not self.api_key:
            logger.warning("OPENAI_API_KEY 없음 — OpenAITTS 비활성화")
            return False
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            speak_speed = speed if speed > 0 else self.default_speed
            response = client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
                speed=speak_speed,
                response_format='wav',
            )
            response.stream_to_file(output_path)
            return Path(output_path).exists()
        except ImportError:
            logger.warning("openai 미설치 — OpenAITTS 비활성화")
            return False
        except Exception as e:
            logger.error(f"OpenAITTS 실패: {e}")
            return False


class ElevenLabsTTS(BaseTTS):
    """ElevenLabs REST API TTS"""

    def __init__(self, cfg: dict):
        self.api_key = os.getenv(cfg.get('api_key_env', 'ELEVENLABS_API_KEY'), '')
        self.model = cfg.get('model', 'eleven_multilingual_v2')
        self.voice_id = cfg.get('voice_id', 'pNInz6obpgDQGcFmaJgB')
        self.stability = cfg.get('stability', 0.5)
        self.similarity_boost = cfg.get('similarity_boost', 0.75)

    def synthesize(self, text: str, output_path: str,
                   lang: str = 'ko', speed: float = 0.0) -> bool:
        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY 없음 — ElevenLabsTTS 비활성화")
            return False
        try:
            import requests as req
            url = (
                f'https://api.elevenlabs.io/v1/text-to-speech/'
                f'{self.voice_id}'
            )
            headers = {
                'xi-api-key': self.api_key,
                'Content-Type': 'application/json',
                'Accept': 'audio/mpeg',
            }
            payload = {
                'text': text,
                'model_id': self.model,
                'voice_settings': {
                    'stability': self.stability,
                    'similarity_boost': self.similarity_boost,
                },
            }
            resp = req.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            # mp3 응답 → 파일 저장 (wav 확장자라도 mp3 데이터 저장 후 ffmpeg 변환)
            mp3_path = str(output_path).replace('.wav', '_tmp.mp3')
            Path(mp3_path).write_bytes(resp.content)
            # mp3 → wav 변환 (ffmpeg 사용)
            ffmpeg = os.getenv('FFMPEG_PATH', 'ffmpeg')
            result = subprocess.run(
                [ffmpeg, '-y', '-loglevel', 'error', '-i', mp3_path,
                 '-ar', '24000', output_path],
                capture_output=True, timeout=60,
            )
            Path(mp3_path).unlink(missing_ok=True)
            return Path(output_path).exists() and result.returncode == 0
        except Exception as e:
            logger.error(f"ElevenLabsTTS 실패: {e}")
            return False


class GTTSEngine(BaseTTS):
    """gTTS 무료 TTS 엔진"""

    def __init__(self, cfg: dict):
        self.default_lang = cfg.get('lang', 'ko')
        self.slow = cfg.get('slow', False)

    def synthesize(self, text: str, output_path: str,
                   lang: str = 'ko', speed: float = 0.0) -> bool:
        try:
            from gtts import gTTS
            use_lang = lang if lang else self.default_lang
            mp3_path = str(output_path).replace('.wav', '_tmp.mp3')
            tts = gTTS(text=text, lang=use_lang, slow=self.slow)
            tts.save(mp3_path)
            # mp3 → wav 변환 (ffmpeg 사용)
            ffmpeg = os.getenv('FFMPEG_PATH', 'ffmpeg')
            result = subprocess.run(
                [ffmpeg, '-y', '-loglevel', 'error', '-i', mp3_path,
                 '-ar', '24000', output_path],
                capture_output=True, timeout=60,
            )
            Path(mp3_path).unlink(missing_ok=True)
            return Path(output_path).exists() and result.returncode == 0
        except ImportError:
            logger.warning("gTTS 미설치 — GTTSEngine 비활성화")
            return False
        except Exception as e:
            logger.warning(f"GTTSEngine 실패: {e}")
            return False


# ─── ImageGenerator 구현체 ─────────────────────────────

class DALLEGenerator(BaseImageGenerator):
    """OpenAI DALL-E 3 이미지 생성 엔진"""

    def __init__(self, cfg: dict):
        self.api_key = os.getenv(cfg.get('api_key_env', 'OPENAI_API_KEY'), '')
        self.model = cfg.get('model', 'dall-e-3')
        self.default_size = cfg.get('size', '1024x1792')
        self.quality = cfg.get('quality', 'standard')

    def generate(self, prompt: str, output_path: str,
                 size: str = '') -> bool:
        if not self.api_key:
            logger.warning("OPENAI_API_KEY 없음 — DALLEGenerator 비활성화")
            return False
        try:
            from openai import OpenAI
            import requests as req
            import io
            from PIL import Image

            use_size = size if size else self.default_size
            client = OpenAI(api_key=self.api_key)
            full_prompt = prompt + ' No text, no letters, no numbers, no watermarks.'
            response = client.images.generate(
                model=self.model,
                prompt=full_prompt,
                size=use_size,
                quality=self.quality,
                n=1,
            )
            img_url = response.data[0].url
            img_bytes = req.get(img_url, timeout=30).content
            img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
            img.save(output_path)
            logger.info(f"DALL-E 이미지 생성 완료: {output_path}")
            return True
        except ImportError as e:
            logger.warning(f"DALLEGenerator 의존성 없음: {e}")
            return False
        except Exception as e:
            logger.error(f"DALLEGenerator 실패: {e}")
            return False


class ExternalGenerator(BaseImageGenerator):
    """수동 이미지 제공 (자동 생성 없음)"""

    def __init__(self, cfg: dict):
        pass

    def generate(self, prompt: str, output_path: str,
                 size: str = '') -> bool:
        logger.info(f"ExternalGenerator: 수동 이미지 필요 — 프롬프트: {prompt[:60]}")
        return False


# ─── EngineLoader ───────────────────────────────────────

class EngineLoader:
    """
    config/engine.json을 읽어 현재 설정된 provider에 맞는 구현체를 반환하는
    중앙 팩토리 클래스.

    사용 예:
        loader = EngineLoader()
        writer = loader.get_writer()
        text = writer.write("오늘의 AI 뉴스 정리해줘")
    """

    _DEFAULT_CONFIG = {
        'writing': {'provider': 'claude', 'options': {'claude': {}}},
        'tts': {'provider': 'gtts', 'options': {'gtts': {}}},
        'image_generation': {'provider': 'external', 'options': {'external': {}}},
        'video_generation': {'provider': 'ffmpeg_slides', 'options': {'ffmpeg_slides': {}}},
        'publishing': {},
        'quality_gates': {'gate1_research_min_score': 60},
    }

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or CONFIG_PATH
        self._config = self._load_config()

    def _load_config(self) -> dict:
        if self._config_path.exists():
            try:
                return json.loads(self._config_path.read_text(encoding='utf-8'))
            except Exception as e:
                logger.error(f"engine.json 로드 실패: {e} — 기본값 사용")
        else:
            logger.warning(f"engine.json 없음 ({self._config_path}) — 기본값으로 gtts + ffmpeg_slides 사용")
        return dict(self._DEFAULT_CONFIG)

    def get_config(self, *keys) -> Any:
        """
        engine.json 값 접근.
        예: loader.get_config('writing', 'provider')
            loader.get_config('quality_gates', 'gate1_research_min_score')
        """
        val = self._config
        for key in keys:
            if isinstance(val, dict):
                val = val.get(key)
            else:
                return None
        return val

    def update_provider(self, category: str, provider: str) -> None:
        """
        런타임 provider 변경 (engine.json 파일은 수정하지 않음).
        예: loader.update_provider('tts', 'openai')
        """
        if category in self._config:
            self._config[category]['provider'] = provider
            logger.info(f"런타임 provider 변경: {category} → {provider}")
        else:
            logger.warning(f"update_provider: 알 수 없는 카테고리 '{category}'")

    def get_writer(self) -> BaseWriter:
        """현재 설정된 writing provider에 맞는 BaseWriter 구현체 반환"""
        writing_cfg = self._config.get('writing', {})
        provider = writing_cfg.get('provider', 'claude')
        options = writing_cfg.get('options', {}).get(provider, {})

        writers = {
            'claude': ClaudeWriter,
            'openclaw': OpenClawWriter,
            'gemini': GeminiWriter,
            'claude_web': ClaudeWebWriter,
            'gemini_web': GeminiWebWriter,
        }
        cls = writers.get(provider, ClaudeWriter)
        logger.info(f"Writer 로드: {provider} ({cls.__name__})")
        return cls(options)

    def get_tts(self) -> BaseTTS:
        """현재 설정된 tts provider에 맞는 BaseTTS 구현체 반환"""
        tts_cfg = self._config.get('tts', {})
        provider = tts_cfg.get('provider', 'gtts')
        options = tts_cfg.get('options', {}).get(provider, {})

        tts_engines = {
            'google_cloud': GoogleCloudTTS,
            'openai': OpenAITTS,
            'elevenlabs': ElevenLabsTTS,
            'gtts': GTTSEngine,
        }
        cls = tts_engines.get(provider, GTTSEngine)
        logger.info(f"TTS 로드: {provider} ({cls.__name__})")
        return cls(options)

    def get_image_generator(self) -> BaseImageGenerator:
        """현재 설정된 image_generation provider에 맞는 구현체 반환"""
        img_cfg = self._config.get('image_generation', {})
        provider = img_cfg.get('provider', 'external')
        options = img_cfg.get('options', {}).get(provider, {})

        generators = {
            'dalle': DALLEGenerator,
            'external': ExternalGenerator,
        }
        cls = generators.get(provider, ExternalGenerator)
        logger.info(f"ImageGenerator 로드: {provider} ({cls.__name__})")
        return cls(options)

    def get_video_generator(self):
        """현재 설정된 video_generation provider에 맞는 VideoEngine 구현체 반환"""
        from bots.converters import video_engine
        video_cfg = self._config.get('video_generation', {
            'provider': 'ffmpeg_slides',
            'options': {'ffmpeg_slides': {}},
        })
        engine = video_engine.get_engine(video_cfg)
        logger.info(f"VideoGenerator 로드: {video_cfg.get('provider', 'ffmpeg_slides')}")
        return engine

    def get_publishers(self) -> list:
        """
        활성화된 publishing 채널 목록 반환.
        반환 형식: [{'name': str, 'enabled': bool, ...설정값}, ...]
        """
        publishing_cfg = self._config.get('publishing', {})
        result = []
        for name, cfg in publishing_cfg.items():
            if isinstance(cfg, dict):
                result.append({'name': name, **cfg})
        return result

    def get_enabled_publishers(self) -> list:
        """enabled: true인 publishing 채널만 반환"""
        return [p for p in self.get_publishers() if p.get('enabled', False)]
