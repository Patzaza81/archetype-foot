import unittest
from pathlib import Path
from unittest.mock import patch

from tools import run_betpawa_loop


class BetPawaLoopTests(unittest.TestCase):
    def test_pipeline_order_is_generator_then_validation_then_runner(self):
        calls = []

        def fake_run(command):
            calls.append(command)

        with patch.object(run_betpawa_loop, "run", side_effect=fake_run), \
             patch.object(run_betpawa_loop.TICKETS, "is_file", return_value=True), \
             patch("subprocess.run") as subprocess_run:
            subprocess_run.return_value.returncode = 0
            with patch("sys.argv", [
                "run_betpawa_loop.py",
                "--ticket-id", "AX-TEST",
                "--click",
            ]):
                run_betpawa_loop.main()

        self.assertEqual(calls[0][1], str(run_betpawa_loop.GENERATOR))
        self.assertEqual(calls[1][1], str(run_betpawa_loop.VALIDATOR))
        runner_call = subprocess_run.call_args.args[0]
        self.assertEqual(runner_call[1], str(run_betpawa_loop.RUNNER))
        self.assertIn("--ticket-id", runner_call)
        self.assertIn("AX-TEST", runner_call)
        self.assertIn("--click", runner_call)

    def test_no_generate_skips_generator_but_keeps_validation(self):
        calls = []

        def fake_run(command):
            calls.append(command)

        with patch.object(run_betpawa_loop, "run", side_effect=fake_run), \
             patch.object(run_betpawa_loop.TICKETS, "is_file", return_value=True), \
             patch("subprocess.run") as subprocess_run:
            subprocess_run.return_value.returncode = 0
            with patch("sys.argv", [
                "run_betpawa_loop.py",
                "--no-generate",
            ]):
                run_betpawa_loop.main()

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], str(run_betpawa_loop.VALIDATOR))


if __name__ == "__main__":
    unittest.main()
