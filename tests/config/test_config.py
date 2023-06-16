from __future__ import annotations


class TestState:
    def test_badness_vs_full_badness(self):
        # For now at least these are expected to differ, thus there should be a test
        # for regression purposes at the very least.
        raise AssertionError


class TestConfig:
    def test_root_cache_dir(self):
        raise AssertionError

    def test_increment_badness(self):
        raise AssertionError

    def test_is_within_badness_threshold(self):
        raise AssertionError

    def test_get_formatted_path(self):
        raise AssertionError

    def test_formatted_current_file_path(self):
        raise AssertionError

    def formatted_target_path(self):
        raise AssertionError
