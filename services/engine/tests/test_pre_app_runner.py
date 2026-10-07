from pathlib import Path
import subprocess

from dantex import pre_app_audit as audit


def test_missing_archive_and_hash_mismatch_fail_closed(tmp_path):
    source, backup = tmp_path/"archive", tmp_path/"backup"
    assert audit.archive_check(source, backup)[0] == "PENDING"
    source.write_bytes(b"source")
    backup.write_bytes(b"backup")
    assert audit.archive_check(source, backup)[0] == "GATED"
    backup.write_bytes(b"source")
    assert audit.archive_check(source, backup)[0] == "GATED"


def test_partial_and_insecure_sink_configuration(monkeypatch):
    monkeypatch.setenv("DANTEX_VALIDATION_REST_URL", "http://example.invalid/table")
    monkeypatch.delenv("DANTEX_VALIDATION_REST_KEY", raising=False)
    assert audit.sink_probe()[0] == "PENDING"
    monkeypatch.setenv("DANTEX_VALIDATION_REST_KEY", "test-key")
    assert audit.sink_probe()[0] == "GATED"


def test_child_checks_scrub_live_credentials_and_preserve_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-value")
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "secret-provider-token")
    monkeypatch.setenv("DANTEX_VALIDATION_REST_KEY", "secret-storage-token")
    def run(command, **kwargs):
        env = kwargs["env"]
        assert "OPENAI_API_KEY" not in env
        assert "UPSTOX_ANALYTICS_TOKEN" not in env
        assert "DANTEX_VALIDATION_REST_KEY" not in env
        return subprocess.CompletedProcess(command, 3, stdout="secret-test-value", stderr="failed")
    monkeypatch.setattr(subprocess, "run", run)
    assert audit.run_command(["test"], tmp_path, tmp_path, "test")[0] == "GATED"
    assert "secret-test-value" not in (tmp_path/"test.log").read_text()


def test_full_run_cannot_green_missing_external_proof(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, "security_check", lambda root: ("CLEAN", "scan"))
    monkeypatch.setattr(audit, "run_command", lambda *args: ("CLEAN", "test"))
    monkeypatch.setattr(audit, "archive_check", lambda *args: ("PENDING", "missing"))
    monkeypatch.setattr(audit, "sink_probe", lambda: ("PENDING", "missing"))
    monkeypatch.setattr(audit, "live_feed_probe", lambda: ("PENDING", "missing"))
    monkeypatch.setattr(audit.shutil, "which", lambda name: "npm")
    from dantex import api
    monkeypatch.setattr(api, "upstox_diagnostic", lambda: {"configured": False})
    output = tmp_path/"report"
    assert audit.main(["--full", "--output", str(output)]) == 2
    assert (output/"report.json").is_file()
    assert not (output/"historical-replay").exists()


def test_existing_report_directory_is_never_overwritten(tmp_path):
    import pytest
    sentinel = tmp_path/"keep"
    sentinel.write_text("evidence")
    with pytest.raises(FileExistsError):
        audit.main(["--output", str(tmp_path)])
    assert sentinel.read_text() == "evidence"


def test_runner_source_root_is_repository():
    assert (audit.ROOT/"services/engine/pyproject.toml").is_file()
    assert isinstance(audit.ROOT, Path)
