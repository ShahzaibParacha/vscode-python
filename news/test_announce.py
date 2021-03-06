# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import codecs
import datetime
import pathlib

import docopt
import pytest

import announce as ann


@pytest.fixture
def directory(tmpdir):
    """Fixture to create a temp directory wrapped in a pathlib.Path object."""
    return pathlib.Path(tmpdir)


def test_news_entry_formatting(directory):
    issue = 42
    normal_entry = directory / f"{issue}.md"
    nonce_entry = directory / f"{issue}-nonce.md"
    body = "Hello, world!"
    normal_entry.write_text(body, encoding="utf-8")
    nonce_entry.write_text(body, encoding="utf-8")
    results = list(ann.news_entries(directory))
    assert len(results) == 2
    for result in results:
        assert result.issue_number == issue
        assert result.description == body


def test_news_entry_sorting(directory):
    oldest_entry = directory / "45.md"
    newest_entry = directory / "123.md"
    oldest_entry.write_text("45", encoding="utf-8")
    newest_entry.write_text("123", encoding="utf-8")
    results = list(ann.news_entries(directory))
    assert len(results) == 2
    assert results[0].issue_number == 45
    assert results[1].issue_number == 123


def test_only_utf8(directory):
    entry = directory / "42.md"
    entry.write_text("Hello, world", encoding="utf-16")
    with pytest.raises(ValueError):
        list(ann.news_entries(directory))


def test_no_bom_allowed(directory):
    entry = directory / "42.md"
    entry.write_bytes(codecs.BOM_UTF8 + "Hello, world".encode("utf-8"))
    with pytest.raises(ValueError):
        list(ann.news_entries(directory))


def test_bad_news_entry_file_name(directory):
    entry = directory / "bunk.md"
    entry.write_text("Hello, world!")
    with pytest.raises(ValueError):
        list(ann.news_entries(directory))


def test_news_entry_README_skipping(directory):
    entry = directory / "README.md"
    entry.write_text("Hello, world!")
    assert len(list(ann.news_entries(directory))) == 0


def test_sections_sorting(directory):
    dir2 = directory / "2 Hello"
    dir1 = directory / "1 World"
    dir2.mkdir()
    dir1.mkdir()
    results = list(ann.sections(directory))
    assert [found.title for found in results] == ["World", "Hello"]


def test_sections_naming(directory):
    (directory / "Hello").mkdir()
    assert not ann.sections(directory)


def test_gather(directory):
    fixes = directory / "2 Fixes"
    fixes.mkdir()
    fix1 = fixes / "1.md"
    fix1.write_text("Fix 1", encoding="utf-8")
    fix2 = fixes / "3.md"
    fix2.write_text("Fix 2", encoding="utf-8")
    enhancements = directory / "1 Enhancements"
    enhancements.mkdir()
    enhancement1 = enhancements / "2.md"
    enhancement1.write_text("Enhancement 1", encoding="utf-8")
    enhancement2 = enhancements / "4.md"
    enhancement2.write_text("Enhancement 2", encoding="utf-8")
    results = ann.gather(directory)
    assert len(results) == 2
    section, entries = results[0]
    assert section.title == "Enhancements"
    assert len(entries) == 2
    assert entries[0].description == "Enhancement 1"
    assert entries[1].description == "Enhancement 2"
    section, entries = results[1]
    assert len(entries) == 2
    assert section.title == "Fixes"
    assert entries[0].description == "Fix 1"
    assert entries[1].description == "Fix 2"


def test_entry_markdown():
    markdown = ann.entry_markdown(ann.NewsEntry(42, "Hello, world!", None))
    assert "42" in markdown
    assert "Hello, world!" in markdown
    assert "https://github.com/Microsoft/vscode-python/issues/42" in markdown


def test_changelog_markdown():
    data = [
        (
            ann.SectionTitle(1, "Enhancements", None),
            [
                ann.NewsEntry(2, "Enhancement 1", None),
                ann.NewsEntry(4, "Enhancement 2", None),
            ],
        ),
        (
            ann.SectionTitle(1, "Fixes", None),
            [ann.NewsEntry(1, "Fix 1", None), ann.NewsEntry(3, "Fix 2", None)],
        ),
    ]
    markdown = ann.changelog_markdown(data)
    assert "### Enhancements" in markdown
    assert "### Fixes" in markdown
    assert "1" in markdown
    assert "Fix 1" in markdown
    assert "2" in markdown
    assert "Enhancement 1" in markdown
    assert "https://github.com/Microsoft/vscode-python/issues/2" in markdown
    assert "3" in markdown
    assert "Fix 2" in markdown
    assert "https://github.com/Microsoft/vscode-python/issues/3" in markdown
    assert "4" in markdown
    assert "Enhancement 2" in markdown


def test_cleanup(directory, monkeypatch):
    rm_path = None

    def fake_git_rm(path):
        nonlocal rm_path
        rm_path = path

    monkeypatch.setattr(ann, "git_rm", fake_git_rm)
    fixes = directory / "2 Fixes"
    fixes.mkdir()
    fix1 = fixes / "1.md"
    fix1.write_text("Fix 1", encoding="utf-8")
    results = ann.gather(directory)
    assert len(results) == 1
    ann.cleanup(results)
    section, entries = results.pop()
    assert len(entries) == 1
    assert rm_path == entries[0].path


TITLE = "# Our most excellent changelog"
OLD_NEWS = f"""\
## 2018.12.0 (31 Dec 2018)

We did things!

## 2017.11.16 (16 Nov 2017)

We started going stuff.
"""
NEW_NEWS = """\
We fixed all the things!

### Code Health

We deleted all the code to fix all the things. ;)
"""


def test_complete_news():
    version = "2019.3.0"
    # Remove leading `0`.
    date = datetime.date.today().strftime("%d %B %Y").lstrip("0")
    news = ann.complete_news(version, NEW_NEWS, f"{TITLE}\n\n\n{OLD_NEWS}")
    expected = f"{TITLE}\n\n## {version} ({date})\n\n{NEW_NEWS.strip()}\n\n\n{OLD_NEWS.strip()}"
    assert news == expected


def test_cli():
    for option in ("--" + opt for opt in ["dry_run", "interim", "final"]):
        args = docopt.docopt(ann.__doc__, [option])
        assert args[option]
    args = docopt.docopt(ann.__doc__, ["./news"])
    assert args["<directory>"] == "./news"
    args = docopt.docopt(ann.__doc__, ["--dry_run", "./news"])
    assert args["--dry_run"]
    assert args["<directory>"] == "./news"
    args = docopt.docopt(ann.__doc__, ["--update", "CHANGELOG.md", "./news"])
    assert args["--update"] == "CHANGELOG.md"
    assert args["<directory>"] == "./news"
