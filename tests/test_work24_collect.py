import argparse
import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "skills" / "work24-collect" / "collect.py"
SPEC = importlib.util.spec_from_file_location("work24_collect", MODULE_PATH)
work24 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = work24
SPEC.loader.exec_module(work24)


XML = """<?xml version="1.0" encoding="UTF-8"?>
<wantedRoot>
  <total>1</total>
  <wanted>
    <wantedAuthNo>K120002611090001</wantedAuthNo>
    <company>테스트 주식회사</company>
    <indTpNm>소프트웨어 개발업</indTpNm>
    <title>데이터 엔지니어</title>
    <salTpNm>연봉</salTpNm><sal>5000만원 이상</sal>
    <region>서울 강남구</region><career>경력 3년</career><minEdubg>대졸</minEdubg>
    <regDt>20261101</regDt><closeDt>20261130</closeDt>
    <wantedInfoUrl>https://www.work24.go.kr/example/1</wantedInfoUrl>
    <empTpCd>10</empTpCd>
  </wanted>
</wantedRoot>"""


def args(**overrides):
    values = dict(
        page=1, limit=20, sort="DESC", query="데이터", region=["서울", "경기"],
        occupation=["133200"], employment=["permanent"], career="E",
        education="05", salary_type="Y", min_pay=4000, max_pay=8000,
        min_career_months=36, max_career_months=120, jobage=14,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


class Work24CollectorTests(unittest.TestCase):
    def test_builds_official_filter_parameters(self):
        params = work24.build_params(args(), "secret-key")
        self.assertEqual(params["region"], "11000|41000")
        self.assertEqual(params["occupation"], "133200")
        self.assertEqual(params["empTp"], "10")
        self.assertEqual(params["career"], "E")
        self.assertEqual(params["regDate"], "W-2")

    def test_parses_normalized_job_posting(self):
        rows = work24.parse_xml(XML, "2026-11-09T00:00:00+00:00")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.external_id, "K120002611090001")
        self.assertEqual(row.title, "데이터 엔지니어")
        self.assertEqual(row.posted_at, "2026-11-01")
        self.assertEqual(row.deadline_date, "2026-11-30")
        self.assertEqual(row.status, "open")
        self.assertIn("기간의 정함이 없는", row.employment_type)

    def test_rejects_api_error_without_leaking_key(self):
        with self.assertRaisesRegex(RuntimeError, "유효하지 않은 인증키"):
            work24.parse_xml("<wantedRoot><message>유효하지 않은 인증키 입니다.</message><messageCd>002</messageCd></wantedRoot>")

    def test_validates_salary_and_experience_ranges(self):
        with self.assertRaisesRegex(ValueError, "min-pay"):
            work24.validate(args(min_pay=None))
        with self.assertRaisesRegex(ValueError, "min-career-months"):
            work24.validate(args(min_career_months=None))


if __name__ == "__main__":
    unittest.main()
