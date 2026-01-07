"""Tests for path_classifier module."""

import pytest
from core.path_classifier import PathClassifier


class TestClassifyPaths:
    """Tests for path classification."""

    def test_classifies_work_path(self, sample_config):
        """Work path patterns match correctly."""
        result = PathClassifier.classify("/home/user/work/project/file.py", sample_config)
        assert result == "work"

    def test_classifies_personal_path(self, sample_config):
        """Personal path patterns match correctly."""
        result = PathClassifier.classify("/home/user/personal/hobby/script.py", sample_config)
        assert result == "personal"

    def test_non_work_path_defaults_to_personal(self, sample_config):
        """Paths not matching work patterns default to personal."""
        result = PathClassifier.classify("/home/user/other/random.py", sample_config)
        assert result == "personal"

    def test_subdirectory_matches_pattern(self, sample_config):
        """Subdirectories of configured paths match."""
        result = PathClassifier.classify("/home/user/work/deep/nested/dir/file.py", sample_config)
        assert result == "work"


class TestExcludedPaths:
    """Tests for path exclusion."""

    def test_tmp_is_excluded(self, sample_config):
        """Paths in /tmp/ are excluded."""
        result = PathClassifier.is_excluded("/tmp/test/file.py", sample_config)
        assert result is True

    def test_cache_is_excluded(self, sample_config):
        """Cache directories are excluded."""
        result = PathClassifier.is_excluded("/home/user/.cache/data.json", sample_config)
        assert result is True

    def test_normal_path_not_excluded(self, sample_config):
        """Normal paths are not excluded."""
        result = PathClassifier.is_excluded("/home/user/work/file.py", sample_config)
        assert result is False


class TestEdgeCases:
    """Tests for edge cases in classification."""

    def test_handles_tilde_expansion(self):
        """Paths with ~ are handled correctly."""
        config = {
            "work_path_patterns": ["~/work/"],
            "personal_path_patterns": ["~/personal/"],
            "excluded_paths": []
        }

        # When path starts with expanded home
        import os
        home = os.path.expanduser("~")
        result = PathClassifier.classify(f"{home}/work/project/file.py", config)
        assert result == "work"

    def test_empty_work_patterns_defaults_to_personal(self):
        """Empty work patterns default all paths to personal."""
        config = {
            "work_path_patterns": [],
            "personal_path_patterns": [],
            "excluded_paths": []
        }

        result = PathClassifier.classify("/any/path/file.py", config)
        assert result == "personal"

    def test_trailing_slash_handling(self, sample_config):
        """Paths with/without trailing slashes match."""
        result1 = PathClassifier.classify("/home/user/work/project", sample_config)
        result2 = PathClassifier.classify("/home/user/work/project/", sample_config)

        assert result1 == result2 == "work"
