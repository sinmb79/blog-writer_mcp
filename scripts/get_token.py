"""
Google OAuth2 토큰 발급 스크립트
실행: python scripts/get_token.py
결과: credentials.json 필요, token.json 생성, refresh_token 출력
"""
import json
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/blogger',
    'https://www.googleapis.com/auth/webmasters',
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube',
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(BASE_DIR, 'token.json')
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')


def main():
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"[ERROR] credentials.json 파일이 없습니다: {CREDENTIALS_PATH}")
        print("Google Cloud Console에서 OAuth 클라이언트 ID를 생성하고")
        print("credentials.json 을 C:\\blog-engine\\ 에 저장하세요.")
        sys.exit(1)

    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            print("[OK] 기존 토큰 갱신 완료")
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
            print("[OK] 새 토큰 발급 완료")

        with open(TOKEN_PATH, 'w') as token_file:
            token_file.write(creds.to_json())

    token_data = json.loads(creds.to_json())
    refresh_token = token_data.get('refresh_token', '')

    print("\n" + "=" * 50)
    print("토큰 발급 성공!")
    print("=" * 50)
    print(f"\nREFRESH_TOKEN:\n{refresh_token}")
    print(f"\n이 값을 .env 파일의 GOOGLE_REFRESH_TOKEN 에 붙여넣으세요.")
    print(f"\ntoken.json 저장 위치: {TOKEN_PATH}")


if __name__ == '__main__':
    main()
