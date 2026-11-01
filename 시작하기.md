# 전체 통합본 실행 방법

이 폴더 하나에 웹 화면, Python API, DB 저장, 백분위, 이상 기록 탐지, 배포 설정이 포함되어 있습니다.

## macOS에서 실행

터미널에서 압축을 푼 프로젝트 폴더로 이동한 뒤:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

브라우저에서 http://localhost:8000 에 접속합니다. 종료는 터미널에서 Ctrl+C.

- 로컬에서는 SQLite 파일이 자동으로 생성됩니다.
- Reveal 버튼을 누르면 서버에 기록이 저장됩니다.
- 같은 보스·부적·종귀 조건의 유효 기록이 20개 미만이면 집계 대기 문구가 나옵니다.
- 처음 보이는 예시와 공유 링크를 여는 동작은 새 기록을 제출하지 않습니다.
- 전체 보스 14명, 영어 UI, 달빛 테마, 카타나·보름달 심볼을 포함합니다.
- 기존 보스 ID와 첨부 ZIP의 예전 ID를 함께 지원합니다.

## 검사

가상환경이 켜진 상태에서 backend 폴더에서:

```sh
python test_api.py
python simulate.py
python detect.py --dry-run
```

합성 데이터 검사는 임시 DB를 사용하며 실제 제출 DB를 채우지 않습니다.

## 배포

Railway용 Dockerfile과 web/cron 설정을 포함했습니다. 실제 Railway 배포와 계정 연결은 수행하지 않았습니다. 기존 chatgpt.site 주소는 이전 정적 버전입니다. 자세한 변수 설정과 실행 구조는 README.md, 검사 결과는 VALIDATION.md에 있습니다.
