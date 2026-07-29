"""Unit tests for the client updater's pure helpers."""

import hashlib
from types import SimpleNamespace

import pytest

import updater


class TestValidateVersion:
    @pytest.mark.parametrize("good", ["1.0.0", "2.0.0-rc.1", "1.0.0_build5", "v3"])
    def test_accepts_normal_release_strings(self, good):
        assert updater.validate_version(good) == good

    @pytest.mark.parametrize(
        "bad",
        ["../evil", "..\\evil", "a/b", "a\\b", "", ".hidden", "-flag", "x" * 100],
    )
    def test_rejects_path_tricks(self, bad):
        with pytest.raises(ValueError):
            updater.validate_version(bad)


class TestVerifySha256:
    def test_matches_and_mismatches(self, tmp_path):
        payload = b"release bytes"
        f = tmp_path / "release.zip"
        f.write_bytes(payload)
        good = hashlib.sha256(payload).hexdigest()
        assert updater.verify_sha256(f, good)
        assert not updater.verify_sha256(f, "0" * 64)


class TestAtomicSwap:
    def test_installs_version_and_flips_pointer(self, tmp_path):
        cfg = SimpleNamespace(install_root=tmp_path)
        staged = tmp_path / "staging" / "1.0.0"
        staged.mkdir(parents=True)
        (staged / "color_app.py").write_text("app", encoding="utf-8")

        updater.atomic_swap(cfg, staged, "1.0.0")

        assert (tmp_path / "current_version").read_text(encoding="utf-8").strip() == "1.0.0"
        assert (tmp_path / "versions" / "1.0.0" / "color_app.py").is_file()
        assert not (tmp_path / "current_version.tmp").exists()

    def test_reinstall_replaces_existing_version_dir(self, tmp_path):
        cfg = SimpleNamespace(install_root=tmp_path)
        old = tmp_path / "versions" / "1.0.0"
        old.mkdir(parents=True)
        (old / "stale.py").write_text("old", encoding="utf-8")
        staged = tmp_path / "staging" / "1.0.0"
        staged.mkdir(parents=True)
        (staged / "color_app.py").write_text("new", encoding="utf-8")

        updater.atomic_swap(cfg, staged, "1.0.0")

        assert not (tmp_path / "versions" / "1.0.0" / "stale.py").exists()
        assert (tmp_path / "versions" / "1.0.0" / "color_app.py").is_file()
