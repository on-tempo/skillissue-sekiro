# Railway PostgreSQL → AWS S3 백업

## 구조와 현재 상태

기존 웹 서비스와 PostgreSQL은 유지합니다. 별도 Railway `backup` 서비스가 하루 한 번 `pg_dump`로 DB를 내보내고 비공개 S3 버킷에 올립니다. DB에 쿼리하지만 테이블을 수정하지 않습니다. 임시 파일은 작업 종료 시 정리됩니다.

이 전달물은 코드와 설정 템플릿입니다. AWS 리소스 생성, 실제 자격증명 발급, 실 DB 접근, S3 업로드 또는 Railway 예약 서비스 생성은 아직 하지 않았습니다. 실제 연결과 복원 시험을 마쳐야 백업을 운영 중이라고 말할 수 있습니다.

## 1. 파일 적용, 검사, 커밋

ZIP을 프로젝트 최상위에 합칩니다. 기존 웹 Dockerfile/requirements는 바꾸지 않습니다. 새 Dockerfile.backup과 backup/requirements.txt는 백업 서비스 전용입니다. 기존 .gitignore, .dockerignore, .github/workflows/ci.yml은 전달한 전체 파일로 교체합니다.

프로젝트 최상위에서:

```sh
python3 -m unittest discover -s backup -p 'test_*.py' -v
```

12개 오프라인 검사는 실제 DB와 AWS를 호출하지 않습니다. 실패 상황, 완료 manifest 순서, URL/비밀값 처리, 빈 DB 복원 보호를 모의 검사합니다. Docker 이미지 빌드는 GitHub CI에서 추가로 검사합니다.

커밋은 다음 명령으로 진행합니다. .env.example은 예시 파일이므로 포함해도 됩니다.

```sh
git add Dockerfile.backup railway.backup.json backup .gitignore .dockerignore .github/workflows/ci.yml BACKUP_SETUP.md
git --no-pager diff --cached --stat
git commit -m "Add scheduled PostgreSQL backups to S3"
```

여기까지가 코드 준비 커밋입니다. AWS 비밀값은 파일에 넣거나 커밋하지 않습니다. bucket placeholder가 있는 IAM 파일은 템플릿 그대로 커밋해도 됩니다. 다음 설정까지 준비한 뒤 `git push origin main`으로 올립니다.

## 2. 먼저 PostgreSQL 연결 확인

Railway에 Postgres 서비스가 있어야 합니다. 웹 서비스 Variables의 DATABASE_URL이 그 서비스의 DATABASE_URL을 참조하는지 확인합니다. 단순히 웹 서비스가 Active이거나 healthz가 성공한 것만으로 PostgreSQL 사용 여부가 증명되지는 않습니다. DATABASE_URL이 없으면 앱은 SQLite를 사용하기 때문입니다.

Postgres가 없다면 먼저 추가하고 웹 서비스의 DATABASE_URL을 연결합니다. 기존 SQLite 기록은 자동 이전되지 않습니다.

## 3. AWS 계정에서 비공개 버킷 생성

AWS 콘솔 → S3 → Create bucket:

- General purpose bucket 선택.
- 전역적으로 고유한 이름 사용. 예: skillissue-db-backups-본인만의접미사.
- 원하는 리전 선택 후 기록해 두기. 예: eu-west-1. Railway DB와 가까운 리전은 전송 지연을 줄일 수 있습니다.
- Object Ownership: ACLs disabled / Bucket owner enforced.
- Block Public Access: 모든 항목 유지.
- Bucket Versioning: Enable.
- Default encryption: SSE-S3 (AES-256).

이 버킷은 공개 웹 이미지용이 아닙니다. DB 백업이 들어갑니다. S3 스토리지·요청·전송과 Railway 작업 실행에는 사용량에 따른 비용이 발생합니다.

## 4. Lifecycle 보관 기간

버킷 Management → Create lifecycle rule에서 postgres/ prefix에 다음을 설정합니다. backup/s3-lifecycle.json에도 같은 규칙이 있습니다. JSON은 AWS CLI/API용이고, 콘솔에서는 항목을 직접 입력합니다.

- Current version: 생성 30일 뒤 만료.
- Noncurrent version: noncurrent가 된 뒤 1일 뒤 영구 삭제.
- 완료되지 않은 multipart upload: 시작 1일 뒤 정리.
- Expired delete marker 정리 규칙도 추가.

버전 관리 버킷의 만료는 곧바로 데이터 영구 삭제를 뜻하지 않습니다. 이전 버전 정리까지 적용해야 하며, Lifecycle 실행은 비동기라 실제 삭제 시점은 정확히 30일로 보장되지 않습니다. 새 프로젝트 전용 버킷에서 이 규칙을 추가하세요. 다른 데이터의 기존 규칙을 덮어쓰지 마세요.

## 5. 백업 전용 IAM 권한

AWS IAM → Policies → Create policy → JSON.

backup/iam-upload-policy.json을 열고 REPLACE_WITH_BUCKET_NAME을 실제 버킷 이름으로 바꿔 콘솔에 붙여 넣습니다. postgres/* 경로의 PutObject와 AbortMultipartUpload만 허용합니다. 버킷 읽기, 목록 조회, 삭제, 공개 설정 권한은 주지 않습니다. 스크립트가 AES256 암호화 업로드를 요청합니다.

IAM → Users에서 백업 전용 사용자를 만들고 이 정책만 연결합니다. 콘솔 로그인 권한은 필요하지 않습니다. 루트 사용자의 access key를 만들지 마세요.

사용자의 Security credentials → Create access key → 외부 AWS 워크로드 용도(Application running outside AWS)에 맞춰 키를 생성합니다. Access key ID와 Secret access key는 Railway backup 서비스 변수에만 입력합니다. 백업 키는 업로드 전용이라 S3 목록을 보는 데 사용할 수 없습니다. 확인과 복원 다운로드는 별도의 운영자 권한으로 합니다.

Railway의 임시 자격증명/워크로드 연동을 별도로 설계한다면 장기 키를 대체할 수 있습니다. 이 첫 구성은 업로드 전용 키를 사용하며, 주기적 교체와 폐기 책임이 있습니다.

## 6. 별도 Railway backup 서비스 생성

웹 서비스와 다른 서비스입니다. 같은 프로젝트·같은 environment에서 같은 GitHub 저장소를 연결하고 이름을 backup으로 지정합니다.

Settings에서:

- Root Directory: 저장소 루트(/).
- Config File Path: /railway.backup.json.
- Dockerfile: Dockerfile.backup. 일반 웹 Dockerfile이 선택되지 않았는지 확인.
- Public domain: 필요 없음.
- Healthcheck: 웹 서비스의 /healthz를 사용하지 않음.

Variables:

| 이름 | 값 |
| --- | --- |
| DATABASE_URL | 같은 Postgres의 참조 변수. 예: ${{Postgres.DATABASE_URL}} |
| BACKUP_S3_BUCKET | 실제 버킷 이름 |
| BACKUP_S3_PREFIX | postgres/ |
| AWS_DEFAULT_REGION | 실제 버킷 리전. 예: eu-west-1 |
| AWS_ACCESS_KEY_ID | 업로드 전용 IAM 키 |
| AWS_SECRET_ACCESS_KEY | 해당 secret key |
| BACKUP_SSLMODE | require (기본값) |

IAM 권한 경로와 prefix가 반드시 일치해야 합니다. 설정 파일은 다른 environment의 DB를 자동 선택하지 않습니다. 변수 참조 대상을 확인합니다. DEVICE_SECRET은 백업에 필요 없습니다.

다음도 확인합니다.

- 원본 DB PostgreSQL major version이 18 이하여야 합니다. 백업 이미지는 PostgreSQL client 18입니다. 더 새 서버에는 client도 올려야 합니다.
- PostgreSQL TLS 연결이 필요합니다. 현재 스크립트는 require, verify-ca, verify-full만 허용합니다. require는 암호화이며 인증서 신원 검증을 완전히 보장하는 모드는 아닙니다. 적절한 CA가 준비됐다면 verify-full과 sslrootcert를 사용합니다.
- Railway 내부 hostname은 Railway 작업 안에서 사용합니다. Mac에서 내부 URL에 직접 연결되지 않는 것은 정상입니다.

## 7. 설정 검사와 첫 실행

코드를 push하고 GitHub Actions를 확인합니다. Railway 예약 서비스가 최종적으로 /railway.backup.json을 읽는지 먼저 확인합니다. 새 repo 서비스를 만드는 순간 기본 railway.json으로 웹 앱이 먼저 시작됐다면, config 경로를 고친 뒤 재배포합니다.

--dry-run은 설정 문자열만 확인합니다. DB 접속, 자격증명 유효성, S3 권한은 확인하지 않습니다. 실제 점검은 backup 서비스의 수동 실행(Run now 등)으로 합니다.

성공 로그:

```text
{"status":"backup_uploaded", "archive_key":"postgres/...dump", ...}
```

AWS S3 콘솔에서 같은 이름의 .dump와 .json 두 파일이 있는지 확인합니다. .json은 .dump 업로드가 끝난 뒤 기록되는 완료 manifest입니다. 둘 중 하나만 있으면 해당 실행을 완료된 백업으로 취급하지 않습니다. 업로드가 실패하면 이미 올라간 파일이 남을 수 있으며 Lifecycle로 정리됩니다.

저장된 SHA-256은 복원 다운로드 파일의 손상 검출에 사용합니다. 공격자가 파일과 manifest 모두를 바꿀 수 있는 상황에 대한 인증 수단은 아닙니다.

## 8. 스케줄과 실패 감시

railway.backup.json의 0 7 * * *는 매일 UTC 07:00입니다. 뉴욕 기준 겨울 02:00, 여름 03:00입니다.

성공이 계속된다는 전제에서 하루치에 가까운 데이터가 백업 간격 사이에 발생할 수 있습니다. 작업 지연/실패가 있으면 손실 가능 구간은 더 길어집니다. 실시간 복제나 장애 자동 전환은 아닙니다.

스크립트 실패는 종료 코드 1로 표시됩니다. 별도 이메일/Slack 알림은 구현하지 않았습니다. 최신 성공 시각과 Railway 실행 로그를 확인하고, 운영 중에는 실패 알림을 별도로 연결하세요.

## 9. 실제 복원 검증

운영 DB에 복원하지 않습니다. 운영과 다른 빈 PostgreSQL 테스트 DB를 준비하고, S3의 같은 실행 .dump와 .json을 다운로드합니다. 운영 버전과 같은 major의 테스트 DB를 사용하는 것이 좋습니다.

restore_verify.py를 사용하는 Python 3.11+ 환경에는 pg_restore와 psql이 필요합니다. 백업 Docker 이미지에는 이미 들어 있습니다. 직접 실행하려면 별도로 설치해야 합니다.

예를 들어 내려받은 파일을 프로젝트의 backup-downloads/에 넣습니다. 이 폴더는 Git/Docker에서 제외됩니다. 로컬에서 테스트용 연결 문자열을 RESTORE_DATABASE_URL 환경변수로 설정하고:

```sh
python backup/restore_verify.py backup-downloads/example.dump backup-downloads/example.json --confirm-empty-target
```

RESTORE_DATABASE_URL에는 오직 테스트 DB를 지정합니다. DATABASE_URL도 함께 주어져 있으면 원본과 동일한 host/port/database인 경우 거부합니다. 이 비교만으로 모든 DB 별칭을 판별할 수는 없으므로 실제 대상도 직접 확인합니다.

복원 도구는 크기·체크섬·archive 목록을 확인하고, 대상에 사용자 relation이 이미 있으면 거부합니다. --clean이나 DROP 명령은 사용하지 않습니다. 복원은 단일 트랜잭션이며, 이후 public.submissions 조회가 가능한지 확인합니다. 원본 snapshot 시점의 건수와 업무 데이터가 맞는지도 추가 점검합니다. 도구만 통과했다고 모든 기능이 검증되는 것은 아닙니다.

오래된 백업을 실제 서비스에 복구하는 경우 만료 기록이 되살아날 수 있습니다. 공개 전 cleanup과 기존 보관 정책을 다시 적용합니다. 백업은 데이터/스키마용이며 Railway 환경변수, AWS 키, DEVICE_SECRET, 클러스터 역할은 별도로 관리합니다.

## 실제 확인 범위

- 오프라인 모의 테스트 12개 통과.
- 실제 PostgreSQL dump/restore와 AWS 업로드는 아직 미검증.
- 로컬 Docker 엔진을 사용한 이미지 실행은 미검증. GitHub CI에서 도구 설치와 오프라인 테스트를 검사하도록 추가.
- AWS 버킷·IAM·Railway 서비스는 사용자가 설정하고 첫 실행/복원 검증 후 완료 판단.
- S3 백업을 실제 활성화하면 web/privacy.html에도 백업 위치·보관 정책 안내를 반영해야 합니다.

## 공식 참고 자료

- PostgreSQL pg_dump: https://www.postgresql.org/docs/current/app-pgdump.html
- S3 IAM 정책: https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-policy-language-overview.html
- S3 Lifecycle: https://docs.aws.amazon.com/AmazonS3/latest/userguide/intro-lifecycle-rules.html