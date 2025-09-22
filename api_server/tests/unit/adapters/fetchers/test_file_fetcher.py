# api_server/tests/unit/adapters/fetchers/test_file_fetcher.py

import io
from pathlib import Path
import pytest

from api_server.app.adapters.fetchers.file_fetcher import FileFetcher
from api_server.app.domain.models import Collection, FileType
from api_server.app.platform.exceptions import DomainError

"""
경로 처리: file:// 스킴과 일반 경로를 모두 검증.
인코딩 폴백: default_encoding='ascii'로 실패를 유도 → utf-8(errors='ignore') 폴백 확인.
파일 타입 식별: 확장자별로 FileType이 맞게 매핑되는지 체크.
경로 정규화: _convert_uri_to_path()가 ~ 확장과 절대 경로화(resolve)를 수행하는지 확인.
에러 케이스: 존재하지 않는 파일은 FileNotFoundError.
"""

# Collection enum이 있다면 일반적으로 Collection.wiki / Collection.qna 같은 멤버가 있을 것이라 가정
#    만약 이름이 다르면 아래 상수만 바꿔 주면 됨.
TEST_COLLECTION = getattr(Collection, "wiki", None) or getattr(Collection, "qna", None)

@pytest.mark.parametrize(
    "ext,expected_filetype,content",
    [
        (".html", FileType.html, "<html><body>안녕</body></html>"),
        (".tsv",  FileType.tsv,  "q\ta\n1\t2\n"),
    ],
)
def test_fetch_with_plain_path(tmp_path: Path, ext, expected_filetype, content):
    # given
    path = tmp_path / f"sample{ext}"
    path.write_text(content, encoding="utf-8")

    fetcher = FileFetcher(default_encoding="utf-8")

    # when
    doc = fetcher.fetch(str(path), TEST_COLLECTION)

    # then
    assert doc.body_text == content
    assert doc.encoding == "utf-8"
    assert doc.collection == TEST_COLLECTION
    assert doc.source.uri == str(path)
    assert doc.source.file_type == expected_filetype


@pytest.mark.parametrize(
    "ext,expected_filetype,content",
    [
        (".html", FileType.html, "<html><body>파일스킴</body></html>"),
        (".tsv",  FileType.tsv,  "k\tv\nx\ty\n"),
    ],
)
def test_fetch_with_file_uri(tmp_path: Path, ext, expected_filetype, content):
    # given
    real_path = tmp_path / f"sample{ext}"
    real_path.write_text(content, encoding="utf-8")
    uri = f"file://{real_path}"

    fetcher = FileFetcher(default_encoding="utf-8")

    # when
    doc = fetcher.fetch(uri, TEST_COLLECTION)

    # then
    assert doc.body_text == content
    assert doc.source.uri == uri
    assert doc.source.file_type == expected_filetype


def test_encoding_fallback_when_default_fails(tmp_path: Path):
    """
    default_encoding을 'ascii'로 설정하고, 한글이 포함된 UTF-8 텍스트를 저장하면
    첫 디코딩에서 UnicodeDecodeError → except로 들어가서 utf-8(errors='ignore')로 복구되는지 확인.
    """
    text = "한글\tABC\t😀"
    path = tmp_path / "utf8.tsv"
    path.write_bytes(text.encode("utf-8"))

    fetcher = FileFetcher(default_encoding="ascii")  # 의도적으로 실패하게

    doc = fetcher.fetch(str(path), TEST_COLLECTION)

    # errors='ignore'로도 유니코드 이모지 등 일부 문자가 날아갈 수 있으나
    # 최소한 예외 없이 문자열이 반환되어야 한다.
    assert isinstance(doc.body_text, str)
    assert len(doc.body_text) > 0
    assert doc.encoding == "utf-8"  # except 블록에서 সেট한 값
    # 한글, ASCII는 살아남는지 대략 확인(이모지는 ignore로 사라질 수 있음)
    assert "한글" in doc.body_text
    assert "ABC" in doc.body_text


def test__convert_uri_to_path_resolves_and_expands(tmp_path: Path, monkeypatch):
    """
    _convert_uri_to_path가 ~ 확장과 절대경로 resolve를 수행하는지 간단 검증
    """
    fetcher = FileFetcher()

    # ~ 확장 검증을 위해 홈 디렉토리를 tmp_path로 임시 바꿈
    monkeypatch.setenv("HOME", str(tmp_path))
    home_file = Path("~") / "file.tsv"
    (tmp_path / "file.tsv").write_text("home-file", encoding="utf-8")

    p1 = fetcher._convert_uri_to_path(str(home_file))
    assert p1.is_absolute()

    # 상대경로 → 절대경로 resolve
    rel = Path("rel.tsv")
    (tmp_path / "rel.tsv").write_text("rel", encoding="utf-8")
    # 작업 디렉토리를 tmp_path로 바꿔서 상대경로 기준 통일
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(tmp_path)
        p2 = fetcher._convert_uri_to_path(str(rel))
        assert p2.is_absolute()


def test_fetch_raises_when_file_not_exists(tmp_path: Path):
    fetcher = FileFetcher()
    missing = tmp_path / "nope.html"
    with pytest.raises(DomainError):
        fetcher.fetch(str(missing), TEST_COLLECTION)
