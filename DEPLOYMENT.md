# React + FastAPI 배포 가이드

## 이번 커밋의 구조

Docker의 Node 22 단계가 `npm ci`와 `npm run build`를 실행합니다. 완성된 `web/dist/`만 Python 실행 이미지에 복사합니다. Python은 `/api/*`와 빌드된 화면을 같은 주소에서 제공합니다. 배포 후 Vite 서버는 필요하지 않습니다.

## 먼저 로컬에서 확인

프로젝트 최상위에서:

```sh
cd web
npm run build
cd ../backend
python test_api.py
```

Python 가상환경이 꺼져 있으면 프로젝트 루트에서 먼저 `source .venv/bin/activate`를 실행하세요.

기존 Python 서버를 Control+C로 종료한 뒤 backend에서:

```sh
uvicorn app:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

http://localhost:8000 에서 React 화면과 Reveal 제출이 모두 동작하면 통합 성공입니다. 이 확인에는 Vite 서버가 필요하지 않습니다.

개발할 때는 계속 Vite 5173 + API 8000을 사용할 수 있습니다. 8000의 정적 화면은 마지막 `npm run build` 시점의 결과이고, 개발 중 최신 화면은 5173에서 확인합니다. 아직 빌드가 없어도 개발용 API는 실행되지만 8000의 메인 화면은 404가 나올 수 있습니다. 프로덕션에서는 빌드 누락 시 시작을 거부합니다.

## 커밋과 push

프로젝트 최상위에서:

```sh
git add Dockerfile .dockerignore backend/app.py backend/test_api.py .github/workflows/ci.yml DEPLOYMENT.md
git --no-pager diff --cached --stat
git commit -m "Build React assets for FastAPI deployment"
git push origin main
```

GitHub 저장소의 Actions에서 `Build and test`를 확인합니다. 타입 검사, React 빌드, SQLite API 검사, Docker 빌드, 컨테이너 안 API 검사를 실행합니다. 실제 PostgreSQL과 Railway 네트워크 동작까지 검사하는 것은 아닙니다.

## Railway에 연결

1. 프로젝트 전체가 올라간 GitHub 저장소로 웹 서비스를 만듭니다. Root Directory는 저장소 루트(`/`)로 둡니다. `web/`이나 `backend/`로 설정하지 마세요.
2. 루트 `Dockerfile`과 `/railway.json`을 사용합니다. 기존 커스텀 Build/Start Command가 있다면 제거하고 Dockerfile의 CMD를 사용합니다. Dockerfile은 Railway의 `PORT`를 읽습니다. Healthcheck는 `/healthz`입니다.
3. PostgreSQL 서비스를 추가하거나 기존 PostgreSQL을 사용합니다. 웹 서비스의 Variables에서 `DATABASE_URL`을 해당 DB의 연결 변수로 설정합니다. 서비스 이름이 Postgres라면 참조 예시는 `${{Postgres.DATABASE_URL}}`입니다.
4. `DEVICE_SECRET`에 충분히 긴 비밀값을 설정합니다. 새 값은 로컬에서 `openssl rand -hex 32`로 만들 수 있습니다. 채팅이나 Git에는 붙여넣지 말고 Railway 변수에만 입력하세요. 기존 비밀값이 있다면 유지합니다.
5. 기존 `WEB_DIR` 변수가 `/app/web` 같은 소스 경로를 가리키면 제거하거나 `/app/web/dist`로 바꿉니다. Dockerfile에는 올바른 기본값이 들어 있습니다.
6. 배포 성공 후 Networking에서 공개 도메인을 생성하거나 기존 도메인을 사용합니다. `/healthz`의 `{"ok":true}`, 메인 화면, 이미지, 기록 제출을 확인합니다.

기존 웹 서비스가 GitHub 자동 배포에 연결돼 있으면 push가 배포를 시작할 수 있습니다. 연결되지 않았다면 GitHub 업로드만 진행됩니다. GitHub Actions 통과를 Railway가 반드시 기다리는 것은 아니므로, 자동 배포를 이미 사용한다면 대시보드에서도 빌드 로그와 healthcheck를 확인하세요.

## 예약 작업

별도 cron 서비스는 같은 저장소와 PostgreSQL을 사용하며 Config File Path는 `/railway.cron.json`입니다. 명령은 `python cleanup.py && python detect.py`이고 1시간마다 실행합니다. web 서비스에 cron 설정을 적용하지 마세요. 둘은 별도 서비스입니다.

`RETENTION_DAYS`를 바꾼다면 web과 cron에 같은 값을 설정합니다. 개인정보 안내도 실제 보관 기간과 일치시킵니다.

## 공개 전 확인

- `web/index.html`의 canonical/OG 도메인 `https://skillissue.gg/`를 실제 사용할 도메인으로 수정합니다.
- 로컬 SQLite 데이터는 자동으로 PostgreSQL에 이전되지 않습니다.
- `TRUST_PROXY_HEADERS`는 검증 전 기본값 0을 유지합니다. 프록시가 전달 헤더를 안전하게 덮어쓰는지 확인한 뒤 필요에 따라 설정합니다. 같은 브라우저를 다른 네트워크에서 사용해 `/api/whoami` 값이 적절히 달라지는지 확인합니다.
- 첫 운영은 웹 복제본 1개로 시작합니다. DB 스키마 생성·제출 제한의 동시성 강화는 별도 작업입니다.
- 이 변경 파일 전달 과정에서 Git push, Railway 계정 설정 또는 실제 배포를 대신 실행하지 않았습니다.

## 이 전달본에서 확인한 것

React 타입 검사·프로덕션 빌드, 빌드 파일 제공, 원본 소스 404, API 저장·점수·중복·제출 제한·14개 보스·기존 ID 호환 검사를 로컬 SQLite로 통과했습니다. 로컬 Docker 엔진이 실행되지 않아 Docker 이미지 자체와 실제 Railway·PostgreSQL 배포는 미검증입니다. CI에 Docker 빌드와 컨테이너 검사를 포함했습니다.