#!/usr/bin/env python3
"""job-searcher :: Work24 official Open API collector.

Reads the Korean Employment Information Service's official Work24/Worknet
recruitment Open API and emits the repository's normalized JobPosting array.
The API key is read from WORK24_API_KEY and is never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SOURCE = "work24"
API_URL = os.environ.get(
    "WORK24_API_URL",
    "https://openapi.work.go.kr/opi/opi/opia/wantedApi.do",
)

REGIONS = {
    "서울": "11000", "seoul": "11000", "11000": "11000",
    "부산": "26000", "busan": "26000", "26000": "26000",
    "대구": "27000", "daegu": "27000", "27000": "27000",
    "인천": "28000", "incheon": "28000", "28000": "28000",
    "광주": "29000", "gwangju": "29000", "29000": "29000",
    "대전": "30000", "daejeon": "30000", "30000": "30000",
    "울산": "31000", "ulsan": "31000", "31000": "31000",
    "세종": "36110", "sejong": "36110", "36110": "36110",
    "경기": "41000", "경기도": "41000", "gyeonggi": "41000", "41000": "41000",
    # The recruitment API's published code table still uses 42000/45000.
    "강원": "42000", "강원도": "42000", "강원특별자치도": "42000", "gangwon": "42000", "42000": "42000",
    "충북": "43000", "충청북도": "43000", "chungbuk": "43000", "43000": "43000",
    "충남": "44000", "충청남도": "44000", "chungnam": "44000", "44000": "44000",
    "전북": "45000", "전라북도": "45000", "전북특별자치도": "45000", "jeonbuk": "45000", "45000": "45000",
    "전남": "46000", "전라남도": "46000", "jeonnam": "46000", "46000": "46000",
    "경북": "47000", "경상북도": "47000", "gyeongbuk": "47000", "47000": "47000",
    "경남": "48000", "경상남도": "48000", "gyeongnam": "48000", "48000": "48000",
    "제주": "50000", "제주도": "50000", "제주특별자치도": "50000", "jeju": "50000", "50000": "50000",
}

EMPLOYMENT = {
    "dispatch": "4", "파견": "4",
    "permanent": "10", "정규": "10", "무기계약": "10",
    "permanent-part-time": "11", "무기계약-시간제": "11",
    "contract": "20", "계약": "20",
    "contract-part-time": "21", "계약-시간제": "21",
    "replacement": "Y", "대체인력": "Y",
}
EMPLOYMENT_LABELS = {
    "4": "파견근로",
    "10": "기간의 정함이 없는 근로계약",
    "11": "기간의 정함이 없는 근로계약(시간선택제)",
    "20": "기간의 정함이 있는 근로계약",
    "21": "기간의 정함이 있는 근로계약(시간선택제)",
    "Y": "대체인력채용",
}
CAREER = {"new": "N", "신입": "N", "experienced": "E", "경력": "E", "any": "Z", "무관": "Z", "N": "N", "E": "E", "Z": "Z"}
EDUCATION = {
    "any": "00", "무관": "00", "00": "00", "elementary": "01", "01": "01",
    "middle": "02", "02": "02", "high-school": "03", "고졸": "03", "03": "03",
    "associate": "04", "전문대": "04", "04": "04", "bachelor": "05", "대졸": "05", "05": "05",
    "master": "06", "석사": "06", "06": "06", "doctor": "07", "박사": "07", "07": "07",
}
SALARY_TYPES = {"daily": "D", "일급": "D", "hourly": "H", "시급": "H", "monthly": "M", "월급": "M", "yearly": "Y", "연봉": "Y", "D": "D", "H": "H", "M": "M", "Y": "Y"}
REG_DATE = {1: "D-0", 3: "D-3", 7: "W-1", 14: "W-2", 30: "M-1"}


@dataclass
class JobPosting:
    source: str
    external_id: str | None
    url: str
    title: str
    company: str | None
    location: str | None
    employment_type: str | None
    posted_at: str | None
    deadline: str | None
    deadline_date: str | None
    status: str
    salary: str | None
    snippet: str | None
    collected_at: str


def _text(node: ET.Element, name: str) -> str | None:
    value = node.findtext(name)
    return value.strip() if value and value.strip() else None


def _iso_date(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _deadline(raw: str | None, today: date) -> tuple[str | None, str]:
    if not raw:
        return None, "unknown"
    if "채용시" in raw or "상시" in raw or "수시" in raw:
        return None, "rolling"
    normalized = _iso_date(raw)
    if not normalized:
        return None, "unknown"
    end = date.fromisoformat(normalized)
    days = (end - today).days
    return normalized, "closed" if days < 0 else ("closing_soon" if days <= 3 else "open")


def _map_many(values: list[str], mapping: dict[str, str], label: str) -> str | None:
    if not values:
        return None
    mapped: list[str] = []
    for raw in values:
        for token in raw.split(","):
            key = token.strip()
            if not key:
                continue
            value = mapping.get(key, mapping.get(key.lower()))
            if not value:
                raise ValueError(f"지원하지 않는 {label} 값: {key}")
            if value not in mapped:
                mapped.append(value)
    return "|".join(mapped) or None


def build_params(args: argparse.Namespace, api_key: str) -> dict[str, str]:
    params = {
        "authKey": api_key,
        "callTp": "L",
        "returnType": "XML",
        "startPage": str(args.page),
        "display": str(args.limit),
        "sortOrderBy": args.sort,
    }
    optional = {
        "keyword": args.query,
        "region": _map_many(args.region, REGIONS, "지역"),
        "occupation": "|".join(args.occupation) if args.occupation else None,
        "empTp": _map_many(args.employment, EMPLOYMENT, "고용형태"),
        "career": CAREER.get(args.career, args.career) if args.career else None,
        "education": EDUCATION.get(args.education, args.education) if args.education else None,
        "salTp": SALARY_TYPES.get(args.salary_type, args.salary_type) if args.salary_type else None,
        "minPay": str(args.min_pay) if args.min_pay is not None else None,
        "maxPay": str(args.max_pay) if args.max_pay is not None else None,
        "minCareerM": str(args.min_career_months) if args.min_career_months is not None else None,
        "maxCareerM": str(args.max_career_months) if args.max_career_months is not None else None,
        "regDate": REG_DATE.get(args.jobage) if args.jobage else None,
    }
    params.update({key: value for key, value in optional.items() if value is not None})
    return params


def parse_xml(xml_text: str, collected_at: str | None = None) -> list[JobPosting]:
    root = ET.fromstring(xml_text)
    message = _text(root, "message") or _text(root, "error")
    code = _text(root, "messageCd")
    rows = root.findall("wanted")
    if message and not rows:
        raise RuntimeError(f"고용24 API 오류{f'({code})' if code else ''}: {message}")
    now = collected_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    today = datetime.fromisoformat(now.replace("Z", "+00:00")).date()
    out: list[JobPosting] = []
    for row in rows:
        external_id = _text(row, "wantedAuthNo")
        title = _text(row, "title")
        url = _text(row, "wantedInfoUrl") or _text(row, "wantedMobileInfoUrl")
        if not external_id or not title or not url:
            continue
        close_raw = _text(row, "closeDt")
        deadline_date, status = _deadline(close_raw, today)
        salary_parts = [part for part in (_text(row, "salTpNm"), _text(row, "sal")) if part]
        snippet_parts = [part for part in (_text(row, "indTpNm"), _text(row, "career"), _text(row, "minEdubg")) if part]
        emp_code = _text(row, "empTpCd")
        out.append(JobPosting(
            source=SOURCE,
            external_id=external_id,
            url=url,
            title=title,
            company=_text(row, "company"),
            location=_text(row, "region") or _text(row, "basicAddr"),
            employment_type=EMPLOYMENT_LABELS.get(emp_code or "", emp_code),
            posted_at=_iso_date(_text(row, "regDt")),
            deadline=close_raw,
            deadline_date=deadline_date,
            status=status,
            salary=" ".join(salary_parts) or None,
            snippet=" · ".join(snippet_parts) or None,
            collected_at=now,
        ))
    return out


def collect(args: argparse.Namespace, api_key: str) -> list[JobPosting]:
    params = build_params(args, api_key)
    request = Request(f"{API_URL}?{urlencode(params)}", headers={"User-Agent": "job-searcher/0.3 (+https://github.com/itssosunny/job-searcher)"})
    with urlopen(request, timeout=args.timeout) as response:
        body = response.read().decode("utf-8")
    return parse_xml(body)


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="고용24 공식 Open API 채용공고 수집기")
    ap.add_argument("--query", "-q", default=None, help="직무·기술·회사 키워드")
    ap.add_argument("--region", action="append", default=[], help="지역명/영문명/공식 코드. 쉼표 또는 반복 지정")
    ap.add_argument("--occupation", action="append", default=[], help="고용24 직종코드. 반복 지정 가능")
    ap.add_argument("--employment", action="append", default=[], help="permanent, contract, dispatch, replacement 등")
    ap.add_argument("--career", choices=sorted(CAREER), help="new, experienced, any 또는 N/E/Z")
    ap.add_argument("--min-career-months", type=int)
    ap.add_argument("--max-career-months", type=int)
    ap.add_argument("--education", choices=sorted(EDUCATION), help="any, high-school, associate, bachelor, master, doctor 등")
    ap.add_argument("--salary-type", choices=sorted(SALARY_TYPES), help="hourly, daily, monthly, yearly 또는 H/D/M/Y")
    ap.add_argument("--min-pay", type=int)
    ap.add_argument("--max-pay", type=int)
    ap.add_argument("--jobage", type=int, choices=sorted(REG_DATE), help="최근 등록일: 1, 3, 7, 14, 30일")
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--limit", "-n", type=int, default=20)
    ap.add_argument("--sort", choices=("DESC", "ASC"), default="DESC")
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--pretty", action="store_true")
    return ap


def validate(args: argparse.Namespace) -> None:
    if not 1 <= args.page <= 1000:
        raise ValueError("--page는 1~1000이어야 합니다")
    if not 1 <= args.limit <= 100:
        raise ValueError("--limit은 1~100이어야 합니다")
    if args.salary_type and (args.min_pay is None or args.max_pay is None):
        raise ValueError("--salary-type 사용 시 --min-pay와 --max-pay가 모두 필요합니다")
    if args.career == "experienced" or args.career == "E":
        if args.min_career_months is None or args.max_career_months is None:
            raise ValueError("경력 검색 시 --min-career-months와 --max-career-months가 모두 필요합니다")


def main(argv: list[str] | None = None) -> int:
    ap = parser()
    args = ap.parse_args(argv)
    try:
        validate(args)
        api_key = os.environ.get("WORK24_API_KEY", "").strip()
        if not api_key:
            raise ValueError("WORK24_API_KEY 환경 변수가 필요합니다. 고용24 기업회원으로 Open API 이용 승인을 먼저 받으세요.")
        postings = collect(args, api_key)
    except Exception as exc:
        print(json.dumps({"source": SOURCE, "error": str(exc), "postings": []}, ensure_ascii=False), file=sys.stderr)
        return 1
    data = [asdict(item) for item in postings]
    print(json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None))
    print(f"{SOURCE}: {len(data)} postings", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
