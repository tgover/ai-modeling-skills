"""Package-level behavior checks. These do not simulate or claim SW execution."""
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/solidworks-cad-modeling"
spec = importlib.util.spec_from_file_location("plate_generator", SKILL / "scripts/generate_plate_macro.py")
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class PlateSourceChecks(unittest.TestCase):
    def test_expected_geometry_and_truthful_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "中文 输出"
            report = generator.generate(directory, r"C:\Templates\零件.prtdot")
            self.assertEqual(report["expected_hole_centers_mm"], [[30, 30], [170, 30], [30, 90], [170, 90]])
            self.assertAlmostEqual(report["expected_volume_mm3"], 480000 - 11520 * math.pi)
            self.assertFalse(report["runtime_modeling_verified"])
            self.assertFalse((directory / "plate.SLDPRT").exists())
            self.assertFalse((directory / "plate.step").exists())
            self.assertEqual(json.loads((directory / "parameters.json").read_text(encoding="utf-8")), report)
            self.assertNotIn("@@", (directory / "plate.bas").read_text(encoding="ascii"))

    def test_reject_impossible_geometry(self):
        for arguments in ((200, 120, 20, 70, 30), (200, 120, 20, 24, 10),
                          (200, 120, 20, 24, 55), (200, 120, 0, 24, 30),
                          (math.nan, 120, 20, 24, 30), (math.inf, 120, 20, 24, 30)):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                generator.check_dimensions(*arguments)

    def test_preserve_existing_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            generator.generate(directory, r"C:\Templates\Part.prtdot")
            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            with self.assertRaises(FileExistsError):
                generator.generate(directory, r"C:\Templates\Part.prtdot", length=210)
            self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})

    def test_unicode_and_quote_roundtrip(self):
        text = '项目 "A" / 模板😀.prtdot'
        expression = generator.vba_string(text)
        expression.encode("ascii")
        tokens = re.findall(r'"(?:[^"]|"")*"|ChrW\$\(&H[0-9A-F]{4}\)', expression)
        raw = bytearray()
        for token in tokens:
            if token.startswith('"'):
                raw.extend(token[1:-1].replace('""', '"').encode("utf-16-le"))
            else:
                raw.extend(int(token[-5:-1], 16).to_bytes(2, "little"))
        self.assertEqual(raw.decode("utf-16-le"), text)

    def test_source_cannot_be_run_as_project(self):
        result = subprocess.run([sys.executable, str(SKILL / "scripts/run_macro.py"),
                                 "--macro", "sample.bas", "--module", "Model"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn(".bas source file cannot be executed directly", result.stderr)


if __name__ == "__main__":
    unittest.main()
