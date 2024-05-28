from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rattr.ast.place import (
    is_in_import_blacklist,
    is_in_pip,
    is_in_stdlib,
)

if TYPE_CHECKING:
    from typing import Final


known_targets_in_stdlib_modules: Final = (
    "os.path",
    "os.path.join",
    "math.sin",
    "math.pi",
)

known_pip_modules: Final = (
    "isort",
    "pytest",
)
known_pip_targets: Final = (
    "isort.place.place_module",
    "pytest.mark.parameterize",
)
known_pip_modules_absent_in_venv: Final = (
    "numpy",
    "pandas",
)


known_rattr_modules: Final = (
    "rattr",
    "rattr.ast.util",
    "rattr.models.context",
)
known_rattr_targets: Final = (
    "rattr.ast.util.basename_of",
    "rattr.models._context.Context",
)


@pytest.fixture
def non_existant_target() -> str:
    return "anything.dotted.anything"


class TestIsInStdlib:
    def test_the_empty_string(self):
        assert not is_in_stdlib("")

    def test_is_non_existant_target(self, non_existant_target):
        assert not is_in_stdlib(non_existant_target)

    def test_is_stdlib_module(self, stdlib_modules):
        for m in stdlib_modules:
            assert is_in_stdlib(m)

    @pytest.mark.parametrize("target", known_targets_in_stdlib_modules)
    def test_is_extant_name_in_stdlib_module(self, target):
        assert is_in_stdlib(target)

    @pytest.mark.parametrize("target", ["math.this.is.not.in.the.stdlib"])
    def test_is_non_existent_name_in_stdlib_module(self, target):
        assert is_in_stdlib(target)

    @pytest.mark.parametrize(
        "target",
        known_pip_modules + known_pip_targets + known_pip_modules_absent_in_venv,
    )
    def test_is_pip_module(self, target):
        assert not is_in_stdlib(target)

    @pytest.mark.parametrize("target", known_rattr_modules + known_rattr_targets)
    def test_is_rattr_module(self, target):
        assert not is_in_stdlib(target)


class TestIsInPip:
    def test_the_empty_string(self):
        assert not is_in_pip("")

    def test_is_non_existant_target(self, non_existant_target):
        assert not is_in_pip(non_existant_target)

    def test_is_stdlib_module(self, stdlib_modules):
        for m in stdlib_modules:
            assert not is_in_pip(m)

    @pytest.mark.parametrize("target", known_targets_in_stdlib_modules)
    def test_is_extant_name_in_stdlib_module(self, target):
        assert not is_in_pip(target)

    @pytest.mark.parametrize("target", ["math.this.is.not.in.the.stdlib"])
    def test_is_non_existent_name_in_stdlib_module(self, target):
        assert not is_in_pip(target)

    @pytest.mark.parametrize("target", known_pip_modules + known_pip_targets)
    def test_is_pip_module(self, target):
        assert is_in_pip(target)

    @pytest.mark.parametrize("target", known_pip_modules_absent_in_venv)
    def test_is_pip_module_not_installed(self, target):
        # This is expected behaviour (otherwise anything on PyPI + any local def'd
        # package would have to be matched).
        assert not is_in_pip(target)

    @pytest.mark.parametrize("target", known_rattr_modules + known_rattr_targets)
    def test_is_rattr_module(self, target):
        assert not is_in_pip(target)


class TestIsInImportBlacklist:
    def test_the_empty_string(self):
        assert is_in_import_blacklist("")

    def test_is_non_existant_target(self, non_existant_target):
        assert not is_in_import_blacklist(non_existant_target)

    def test_is_stdlib_module(self, stdlib_modules):
        for m in stdlib_modules:
            assert not is_in_import_blacklist(m)

    @pytest.mark.parametrize("target", known_targets_in_stdlib_modules)
    def test_is_extant_name_in_stdlib_module(self, target):
        assert not is_in_import_blacklist(target)

    @pytest.mark.parametrize(
        "banned,unbanned",
        [({"beelzebub", "abaddon"}, {"michael", "raphael", "gabriel"})],
    )
    def test_from_argument(self, arguments, banned, unbanned):
        # Nothing is banned
        with arguments(_excluded_imports=set()):
            for banned_module in banned:
                assert not is_in_import_blacklist(banned_module)
            for unbanned_module in unbanned:
                assert not is_in_import_blacklist(unbanned_module)

        # Only bad things are banned
        with arguments(_excluded_imports=banned):
            for banned_module in banned:
                assert is_in_import_blacklist(banned_module)
            for unbanned_module in unbanned:
                assert not is_in_import_blacklist(unbanned_module)

    @pytest.mark.parametrize(
        "target",
        known_pip_modules + known_pip_targets + known_pip_modules_absent_in_venv,
    )
    def test_is_pip_module_not_installed(self, arguments, target):
        with arguments(_excluded_imports=set()):
            assert not is_in_import_blacklist(target)

        with arguments(_excluded_imports={target}):
            assert is_in_import_blacklist(target)

    @pytest.mark.parametrize("target", known_rattr_modules + known_rattr_targets)
    def test_always_blacklist_rattr(self, target):
        assert is_in_import_blacklist(target)
