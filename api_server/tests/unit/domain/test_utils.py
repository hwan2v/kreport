import re
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from api_server.app.domain import utils
from api_server.app.domain.models import FileType, Collection

def test_infer_date_from_path_returns_datetime_with_offset(monkeypatch):
    """
    파일 경로에서 날짜를 추출하는 함수.
    """

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

    # day_3 -> now() - 3일
    assert isinstance(result, datetime)
    assert result == fixed_now - timedelta(days=3)


def test_infer_date_from_path_with_invalid_path_raises():
    """
    잘못된 파일 경로에서 날짜 추출 -> 에러
    day_X 형식이 없으면 IndexError 발생 가능
    """
    with pytest.raises(IndexError):
        utils.infer_date_from_path("invalid/path/file.tsv")


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("doc.html", FileType.html),
        ("doc.htm", FileType.html),
        ("file.tsv", FileType.tsv),
    ],
)
def test_ext_to_file_type_known_extensions(filename, expected):
    """
    파일 확장자에서 파일 타입을 추출하는 함수.
    """

    result = utils.ext_to_file_type(Path(filename))
    assert result == expected


def test_choose_collection_html_and_tsv():
    """
    파일 타입에 따라 컬렉션을 선택하는 함수.
    """
    assert utils.choose_collection(FileType.html) == Collection.wiki
    assert utils.choose_collection(FileType.tsv) == Collection.qna


def test_choose_collection_invalid_type():
    """
    존재하지 않는 FileType 을 넘기면 ValueError
    """
    class DummyFileType(str):
        pass

    with pytest.raises(ValueError):
        utils.choose_collection("pdf")
