import unittest
from pathlib import Path


class WindowsLauncherTest(unittest.TestCase):
    def setUp(self):
        self.launcher_text = Path("start_career_radar.bat").read_text(
            encoding="utf-8",
        )

    def test_launcher_prefers_venv_python(self):
        self.assertIn('if exist ".venv\\Scripts\\python.exe"', self.launcher_text)
        self.assertIn(
            'set "PYTHON_EXE=%CD%\\.venv\\Scripts\\python.exe"',
            self.launcher_text,
        )

    def test_launcher_falls_back_to_global_python(self):
        self.assertIn("python --version >nul 2>&1", self.launcher_text)
        self.assertIn('set "PYTHON_EXE=python"', self.launcher_text)

    def test_launcher_error_path_explains_how_to_recover(self):
        self.assertIn("if not defined PYTHON_EXE", self.launcher_text)
        self.assertIn("Python was not found.", self.launcher_text)
        self.assertIn("python -m venv .venv", self.launcher_text)
        self.assertIn(
            ".venv\\Scripts\\python.exe -m pip install -r requirements.txt",
            self.launcher_text,
        )


if __name__ == "__main__":
    unittest.main()
