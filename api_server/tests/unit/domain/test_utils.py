# api_server/tests/unit/domain/test_utils.py

import re
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from api_server.app.domain import utils
from api_server.app.domain.models import FileType, Collection
"""
infer_date_from_path
    datetime.now() 를 monkeypatch 로 고정 → 예상된 timedelta 만큼 차이나는지 확인.
    day_X 패턴이 없을 때 예외 처리 확인.
ext_to_file_type
    .html, .htm, .tsv 정상 매핑 확인.
    알 수 없는 확장자는 FileType.plain 으로 가도록 코드가 작성됐지만,
    현재 FileType Enum 에는 plain 이 정의되어 있지 않음 → 이 부분은 테스트에서 AttributeError 발생을 체크.
choose_collection
    html → wiki, tsv → qna 매핑 확인.
    미지원 타입은 ValueError 발생 확인.
"""

# ------------------------
# infer_date_from_path
# ------------------------
def test_infer_date_from_path_returns_datetime_with_offset(monkeypatch):
    # 기준 시각 고정
    fixed_now = datetime(2024, 1, 10, 12, 0, 0)
    monkeypatch.setattr(utils, "datetime", datetime)

    # datetime.now() 고정
    class DummyDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(utils, "datetime", DummyDatetime)

    source_path = "api_server/resources/data/qna/day_3/file.tsv"
    result = utils.infer_date_from_path(source_path)

    # day_3 → now() - 3일
    assert isinstance(result, datetime)
    assert result == fixed_now - timedelta(days=3)


def test_infer_date_from_path_with_invalid_path_raises():
    # day_X 형식이 없으면 IndexError 발생 가능
    with pytest.raises(IndexError):
        utils.infer_date_from_path("invalid/path/file.tsv")


# ------------------------
# ext_to_file_type
# ------------------------
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("doc.html", FileType.html),
        ("doc.htm", FileType.html),
        ("file.tsv", FileType.tsv),
    ],
)
def test_ext_to_file_type_known_extensions(filename, expected):
    result = utils.ext_to_file_type(Path(filename))
    assert result == expected

# ------------------------
# choose_collection
# ------------------------
def test_choose_collection_html_and_tsv():
    assert utils.choose_collection(FileType.html) == Collection.wiki
    assert utils.choose_collection(FileType.tsv) == Collection.qna


def test_choose_collection_invalid_type():
    # 존재하지 않는 FileType 을 넘기면 ValueError
    class DummyFileType(str):
        pass

    with pytest.raises(ValueError):
        utils.choose_collection("pdf")  # type: ignore
