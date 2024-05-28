from __future__ import annotations

from pathlib import Path
from unittest import mock

from rattr.config._util import _is_project_root
from rattr.config.util import find_xdg_cache_dir


def mock_path(
    loc: str,
    *,
    is_dir: bool = False,
    is_file: bool = False,
):
    m_path = mock.Mock(spec=Path)

    m_path.__str__ = lambda _self: loc

    m_path.is_dir.return_value = is_dir
    m_path.is_file.return_value = is_file
    m_path.exists.return_value = is_dir or is_file

    return m_path


class TestIsProjectRoot:
    def test_is_not_dir(self):
        # Definitionally a root directory must be a directory!
        assert not _is_project_root(mock_path("/some/file.txt", is_dir=False))


class TestFindXdgCacheDir:
    @mock.patch("rattr.config.util.os")
    @mock.patch("rattr.config.util.Path")
    def test_user_xdg_cache_home_is_set(self, m_path, m_os):
        xdg_cache_home = "/home/user/.my_custom_cache"

        m_path.side_effect = lambda loc: mock_path(loc, is_dir=True)
        m_os.environ = {"XDG_CACHE_HOME": xdg_cache_home}

        assert str(find_xdg_cache_dir()) == xdg_cache_home

    @mock.patch("rattr.config.util.os")
    def test_user_xdg_cache_home_is_not_set(self, m_os):
        m_os.environ = {}
        assert str(find_xdg_cache_dir()) == str(Path.home() / ".cache")
