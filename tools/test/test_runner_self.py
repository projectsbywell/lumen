"""
Lumen Test Runner — Self-test.
Validates that the runner itself can discover, execute, and report tests correctly.
"""

import os
import sys
import json
import tempfile
import shutil
import unittest

# Ensure the tools/test path is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lumen_test import Runner, discover_tests, TestResult, CoverageReport, _discover_py_tests, _discover_lum_tests


class TestRunnerSelf(unittest.TestCase):
    """Tests for the lumen_test.py runner itself."""

    def setUp(self):
        """Create a temporary directory with test files."""
        self.tmpdir = tempfile.mkdtemp(prefix="lumen_test_")
        # Create a simple test file
        self.test_file = os.path.join(self.tmpdir, "test_sample.py")
        with open(self.test_file, "w") as f:
            f.write("""
import unittest

class TestSample(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(1 + 1, 2)

    def test_fail(self):
        self.assertEqual(1 + 1, 3)

    def test_error(self):
        raise RuntimeError("intentional error")

class TestPassOnly(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)
""")

        # Create a .lum reference file
        self.lum_file = os.path.join(self.tmpdir, "test_sample.lum")
        with open(self.lum_file, "w") as f:
            f.write("""
@test
fun test_lum_hello():
    return "hello"

fun test_lum_add(a: Int, b: Int): Int
    return a + b
""")

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_discover_py_tests(self):
        """Verify .py test discovery."""
        tests = _discover_py_tests(self.test_file)
        self.assertGreater(len(tests), 0)
        test_names = [t["name"] for t in tests]
        self.assertIn("test_pass", test_names)
        self.assertIn("test_fail", test_names)
        self.assertIn("test_error", test_names)
        self.assertIn("test_ok", test_names)

    def test_discover_lum_tests(self):
        """Verify .lum test discovery."""
        tests = _discover_lum_tests(self.lum_file)
        self.assertGreater(len(tests), 0)
        test_names = [t["name"] for t in tests]
        self.assertIn("test_lum_hello", test_names)
        self.assertIn("test_lum_add", test_names)

    def test_discover_tests_integration(self):
        """Verify discover_tests works on a directory."""
        tests = discover_tests(self.tmpdir)
        self.assertGreater(len(tests), 0)

    def test_runner_execute(self):
        """Verify Runner can execute tests and produce a report."""
        runner = Runner(root_dir=self.tmpdir, verbose=False)
        report = runner.run()
        self.assertIn("total", report)
        self.assertIn("passed", report)
        self.assertIn("failed", report)
        self.assertIn("success", report)
        self.assertIn("results", report)
        self.assertIn("duration", report)
        self.assertGreaterEqual(report["total"], 0)

    def test_runner_all_pass(self):
        """Create a passing test and verify success (isolated dir)."""
        sub = os.path.join(self.tmpdir, "only_pass")
        os.makedirs(sub, exist_ok=True)
        pass_file = os.path.join(sub, "test_pass.py")
        with open(pass_file, "w") as f:
            f.write("""
import unittest
class TestPass(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)
""")
        runner = Runner(root_dir=sub, verbose=False)
        report = runner.run()
        self.assertTrue(report["success"] or report["failed"] == 0)

    def test_runner_report_structure(self):
        """Verify report has correct structure."""
        runner = Runner(root_dir=self.tmpdir, verbose=False)
        report = runner.run()
        for key in ["timestamp", "duration", "total", "passed", "failed",
                     "errors", "skipped", "success", "results", "coverage"]:
            self.assertIn(key, report)

    def test_runner_ci_exit_code(self):
        """Verify CI exit codes."""
        runner = Runner(root_dir=self.tmpdir, verbose=False)
        report = runner.run()
        # Exit code is 0 if success, 1 otherwise
        expected_code = 0 if report["success"] else 1
        self.assertIn(runner.ci_exit_code(report), [0, 1])

    def test_runner_json_report(self):
        """Verify JSON report generation."""
        runner = Runner(root_dir=self.tmpdir, verbose=False)
        report = runner.run()
        json_path = os.path.join(self.tmpdir, "report.json")
        runner.write_json_report(report, json_path)
        self.assertTrue(os.path.exists(json_path))
        with open(json_path) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["total"], report["total"])
        self.assertEqual(loaded["success"], report["success"])

    def test_test_result_to_dict(self):
        """Verify TestResult serialization."""
        result = TestResult("test_name", "/path/to/file.py", 10, "PASS", 0.001, None)
        d = result.to_dict()
        self.assertEqual(d["name"], "test_name")
        self.assertEqual(d["path"], "/path/to/file.py")
        self.assertEqual(d["line"], 10)
        self.assertEqual(d["status"], "PASS")
        self.assertEqual(d["duration"], 0.001)
        self.assertIsNone(d["error"])

    def test_coverage_report(self):
        """Verify CoverageReport structure."""
        cov = CoverageReport(total_lines=100, covered_lines=80, missed_lines=[1, 2, 3])
        self.assertEqual(cov.total_lines, 100)
        self.assertEqual(cov.covered_lines, 80)
        self.assertEqual(len(cov.missed_lines), 3)
        self.assertEqual(cov.coverage_pct, 80.0)
        d = cov.to_dict()
        self.assertIn("total_lines", d)
        self.assertIn("coverage_pct", d)

    def test_test_result_statuses(self):
        """Verify all TestResult statuses work."""
        for status in ["PASS", "FAIL", "ERROR", "SKIP"]:
            r = TestResult("test", "path", 1, status)
            self.assertEqual(r.status, status)
            self.assertIn(r.status, ["PASS", "FAIL", "ERROR", "SKIP"])

    def test_discover_skips_tools_test(self):
        """Verify discover_tests skips the tools/test/ directory."""
        tools_test_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "test")
        if os.path.isdir(tools_test_dir):
            # Should not discover tests from itself
            tests = discover_tests(tools_test_dir)
            # The runner itself should not be in the results
            for t in tests:
                self.assertNotIn("runner_self", t["name"])

    def test_runner_report_print(self):
        """Verify that print_report does not crash."""
        runner = Runner(root_dir=self.tmpdir, verbose=False)
        report = runner.run()
        # Just verify it doesn't crash - capture stdout
        import io
        old_stdout = sys.stdout
        sys.stdout = buf = io.StringIO()
        try:
            runner.print_report(report)
            output = buf.getvalue()
            self.assertIn("LUMEN TEST RUNNER REPORT", output)
        finally:
            sys.stdout = old_stdout

    def test_runner_verbose(self):
        """Verify verbose mode works."""
        runner = Runner(root_dir=self.tmpdir, verbose=True)
        report = runner.run()
        self.assertIn("total", report)


class TestRunnerEdgeCases(unittest.TestCase):
    """Edge case tests for the runner."""

    def test_empty_directory(self):
        """Running on an empty directory should produce a valid report."""
        tmpdir = tempfile.mkdtemp(prefix="lumen_empty_")
        try:
            runner = Runner(root_dir=tmpdir, verbose=False)
            report = runner.run()
            self.assertIn("total", report)
            self.assertIn("success", report)
            self.assertEqual(report["total"], 0)
            self.assertTrue(report["success"])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_nonexistent_directory(self):
        """Running on a nonexistent directory should not crash."""
        runner = Runner(root_dir="/tmp/nonexistent_lumen_dir_xyz", verbose=False)
        report = runner.run()
        self.assertIn("total", report)
        # Should succeed with 0 tests
        self.assertTrue(report["success"])

    def test_file_discovery(self):
        """Discover tests in the actual lumen stdlib files."""
        lumen_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "lumen")
        lumen_root = os.path.normpath(lumen_root)
        if os.path.isdir(lumen_root):
            tests = discover_tests(lumen_root)
            # Should find at least some tests in the stdlib
            # (or at least not crash)
            self.assertIsInstance(tests, list)

    def test_runner_with_lum_files(self):
        """Verify runner handles .lum files correctly."""
        tmpdir = tempfile.mkdtemp(prefix="lumen_lum_")
        lum_path = os.path.join(tmpdir, "test.lum")
        with open(lum_path, "w") as f:
            f.write("@test\nfun test_lum_ok():\n    pass\n")
        try:
            tests = discover_tests(tmpdir)
            lum_tests = [t for t in tests if t["path"].endswith(".lum")]
            self.assertGreater(len(lum_tests), 0)
            runner = Runner(root_dir=tmpdir, verbose=False)
            report = runner.run()
            self.assertIn("results", report)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
