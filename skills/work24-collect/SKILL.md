---
name: work24-collect
description: 승인된 고용24 기업회원이 공식 Open API에서 대한민국 채용공고를 지역·직종·경력·학력·고용형태·급여 조건으로 검색해 정규화 JSON으로 수집합니다. 개인회원은 사용할 수 없습니다. Read-only; 로그인·저장·지원은 하지 않습니다.
---

# 고용24 공식 API 수집기

한국고용정보원의 고용24 채용정보 Open API를 GET으로 조회하고 `docs/SCHEMA.md`의
`JobPosting` 배열로 출력합니다. 공개 HTML을 크롤링하지 않습니다.

> **기업회원 전용:** 개인회원은 이 API를 사용할 수 없습니다. 이 수집기는 개인 사용자
> 기본 검색에 포함하지 않으며, 고용24 심사를 통과한 기업회원만 승인 목적 안에서 사용합니다.

## 준비

고용24의 [Open API 안내](https://www.work24.go.kr/cm/e/a/0110/selectOpenApiIntro.do)에
따라 기업회원으로 이용 신청·심사를 마친 뒤 발급받은 키를 환경 변수에 설정합니다.

```bash
export WORK24_API_KEY="발급받은-키"        # PowerShell: $env:WORK24_API_KEY="발급받은-키"
python3 skills/work24-collect/collect.py --query "데이터 엔지니어" --region 서울 --jobage 14 --limit 20
```

인증키를 코드·로그·커밋에 넣지 마세요. 이 저장소의 `.gitignore`는 `.env*`를 제외하지만,
수집기는 `.env`를 직접 읽지 않습니다.

## 주요 조건

- `--region`: 서울, 경기, 인천 같은 지역명, 영문명 또는 공식 코드. 여러 번 지정 가능
- `--occupation`: 고용24 직종코드. 여러 번 지정 가능
- `--employment`: `permanent`, `contract`, `dispatch`, `replacement` 등
- `--career`: `new`, `experienced`, `any` (`experienced`는 최소·최대 경력 개월 필수)
- `--education`: `any`, `high-school`, `associate`, `bachelor`, `master`, `doctor`
- `--salary-type`: `hourly`, `daily`, `monthly`, `yearly` (최소·최대 급여 필수)
- `--jobage`: `1`, `3`, `7`, `14`, `30`

공식 문서상 영리법인(개인사업자 포함)은 채용정보 API를 사용할 수 없습니다. 발급받은
인증키의 승인 목적과 고용24 이용약관 안에서만 사용하세요.
