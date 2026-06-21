"""Unit tests for core.logger"""
import os
import logging
import tempfile
import pytest

from core.logger import TaskLogger


class TestFormatSize:
    def test_zero_bytes(self):
        assert TaskLogger.format_size(0) == "0 B"

    def test_negative_treated_as_zero(self):
        assert TaskLogger.format_size(-100) == "0 B"

    def test_bytes(self):
        assert TaskLogger.format_size(512) == "512 B"

    def test_one_kb(self):
        assert TaskLogger.format_size(1024) == "1.0 KB"

    def test_kilobytes(self):
        assert TaskLogger.format_size(1536) == "1.5 KB"

    def test_one_mb(self):
        assert TaskLogger.format_size(1024 * 1024) == "1.0 MB"

    def test_megabytes(self):
        result = TaskLogger.format_size(int(2.3 * 1024 * 1024))
        assert result == "2.3 MB"

    def test_one_gb(self):
        assert TaskLogger.format_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_gigabytes(self):
        result = TaskLogger.format_size(int(1.5 * 1024 * 1024 * 1024))
        assert result == "1.5 GB"

    def test_boundary_1023_bytes(self):
        assert TaskLogger.format_size(1023) == "1023 B"

    def test_boundary_1023_kb(self):
        val = 1024 * 1024 - 1
        result = TaskLogger.format_size(val)
        assert "KB" in result


class TestTaskLoggerSession:
    def test_start_creates_log_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger(log_dir=tmpdir)
            log_path = logger.start_session()
            assert log_path is not None
            assert os.path.exists(log_path)
            assert log_path.endswith(".log")
            logger.stop_session()

    def test_stop_session_clears_handler(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger(log_dir=tmpdir)
            logger.start_session()
            logger.stop_session()
            assert logger._file_handler is None
            assert logger._current_log_file is None

    def test_stop_without_start_is_noop(self):
        logger = TaskLogger(log_dir="/tmp/nonexistent")
        logger.stop_session()

    def test_start_stops_previous_session(self):
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger(log_dir=tmpdir)
            path1 = logger.start_session()
            time.sleep(1.1)
            path2 = logger.start_session()
            assert path1 != path2
            logger.stop_session()

    def test_log_file_name_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger(log_dir=tmpdir)
            log_path = logger.start_session()
            filename = os.path.basename(log_path)
            assert filename.startswith("task_")
            assert filename.endswith(".log")
            logger.stop_session()


class TestTaskLoggerEmit:
    def test_info_writes_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger(log_dir=tmpdir)
            log_path = logger.start_session()
            logger.info("test message")
            logger.stop_session()

            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "test message" in content

    def test_warning_writes_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger(log_dir=tmpdir)
            log_path = logger.start_session()
            logger.warning("warn msg")
            logger.stop_session()

            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "warn msg" in content
            assert "WARNING" in content

    def test_error_writes_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger(log_dir=tmpdir)
            log_path = logger.start_session()
            logger.error("error msg")
            logger.stop_session()

            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "error msg" in content
            assert "ERROR" in content

    def test_success_writes_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger(log_dir=tmpdir)
            log_path = logger.start_session()
            logger.success("success msg")
            logger.stop_session()

            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "success msg" in content
            assert "SUCCESS" in content

    def test_gui_callback_called(self):
        received = []

        def callback(level, msg):
            received.append((level, msg))

        logger = TaskLogger(gui_callback=callback)
        logger.info("hello")
        assert len(received) == 1
        assert received[0] == ("INFO", "hello")

    def test_gui_callback_exception_suppressed(self):
        def bad_callback(level, msg):
            raise RuntimeError("boom")

        logger = TaskLogger(gui_callback=bad_callback)
        logger.info("should not crash")

    def test_set_gui_callback(self):
        received = []
        logger = TaskLogger()
        logger.set_gui_callback(lambda level, msg: received.append(msg))
        logger.info("test")
        assert "test" in received

    def test_set_gui_callback_to_none(self):
        logger = TaskLogger(gui_callback=lambda l, m: None)
        logger.set_gui_callback(None)
        logger.info("no crash")

    def test_error_with_exc_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger(log_dir=tmpdir)
            log_path = logger.start_session()
            try:
                raise ValueError("test error")
            except ValueError:
                logger.error("caught error", exc_info=True)
            logger.stop_session()

            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "ValueError" in content


class TestGetLogFiles:
    def test_nonexistent_directory(self):
        result = TaskLogger.get_log_files("/tmp/nonexistent_dir_12345")
        assert result == []

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = TaskLogger.get_log_files(tmpdir)
            assert result == []

    def test_returns_log_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["task_20250101_120000.log", "task_20250102_120000.log"]:
                with open(os.path.join(tmpdir, name), "w") as f:
                    f.write("log content")

            result = TaskLogger.get_log_files(tmpdir)
            assert len(result) == 2
            assert all("name" in entry for entry in result)
            assert all("path" in entry for entry in result)
            assert all("size_bytes" in entry for entry in result)
            assert all("date" in entry for entry in result)

    def test_sorted_newest_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import time
            path1 = os.path.join(tmpdir, "old.log")
            with open(path1, "w") as f:
                f.write("old")
            time.sleep(0.05)
            path2 = os.path.join(tmpdir, "new.log")
            with open(path2, "w") as f:
                f.write("new")

            result = TaskLogger.get_log_files(tmpdir)
            assert result[0]["name"] == "new.log"

    def test_ignores_non_log_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "readme.txt"), "w") as f:
                f.write("not a log")
            with open(os.path.join(tmpdir, "task.log"), "w") as f:
                f.write("a log")

            result = TaskLogger.get_log_files(tmpdir)
            assert len(result) == 1
            assert result[0]["name"] == "task.log"


class TestClearAllLogs:
    def test_nonexistent_directory(self):
        deleted, freed = TaskLogger.clear_all_logs("/tmp/nonexistent_12345")
        assert deleted == 0
        assert freed == 0

    def test_clears_log_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["a.log", "b.log"]:
                with open(os.path.join(tmpdir, name), "w") as f:
                    f.write("x" * 100)

            deleted, freed = TaskLogger.clear_all_logs(tmpdir)
            assert deleted == 2
            assert freed == 200
            assert len(os.listdir(tmpdir)) == 0

    def test_preserves_non_log_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "keep.txt"), "w") as f:
                f.write("keep")
            with open(os.path.join(tmpdir, "delete.log"), "w") as f:
                f.write("delete")

            deleted, _ = TaskLogger.clear_all_logs(tmpdir)
            assert deleted == 1
            remaining = os.listdir(tmpdir)
            assert "keep.txt" in remaining


class TestGetLogsTotalSize:
    def test_nonexistent_directory(self):
        result = TaskLogger.get_logs_total_size("/tmp/nonexistent_12345")
        assert result == "0 B"

    def test_calculates_total(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["a.log", "b.log"]:
                with open(os.path.join(tmpdir, name), "w") as f:
                    f.write("x" * 512)

            result = TaskLogger.get_logs_total_size(tmpdir)
            assert "KB" in result or "B" in result
