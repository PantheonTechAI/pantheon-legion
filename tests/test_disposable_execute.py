import unittest

from tests.federation.execute import main


class DisposableExecuteTests(unittest.TestCase):
    def test_refuses_to_start_without_explicit_execute_flag(self):
        with self.assertRaises(SystemExit) as exit_info:
            main([
                "--tabula-root", "/disposable/tabula",
                "--project-name", "pantheon-federation-test",
                "--env-file", "/disposable/tabula/.env",
            ])
        self.assertEqual(exit_info.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
