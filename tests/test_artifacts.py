import tempfile
import unittest
import zipfile
from pathlib import Path

from catalog.artifacts import inspect_icon, inspect_package

from helpers import package_entries, write_zip


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "artifact.zip"

    def tearDown(self):
        self.tmp.cleanup()

    def inspect(self, entries):
        write_zip(self.path, entries)
        return inspect_package(self.path, "PPSA01234")

    def assertProblem(self, entries, fragment):
        errors = self.inspect(entries).errors
        self.assertTrue(any(fragment in e for e in errors), f"{fragment!r} not in {errors}")

    def test_valid_package(self):
        result = self.inspect(package_entries())
        self.assertEqual(result.errors, [])
        self.assertEqual(result.param["contentVersion"], "01.000.000")
        self.assertEqual(result.files, 3)

    def test_not_a_zip(self):
        self.path.write_bytes(b"not a zip")
        self.assertIn("not a valid ZIP", inspect_package(self.path, "PPSA01234").errors[0])

    def test_contents_must_sit_in_title_folder(self):
        entries = package_entries()
        entries["README.txt"] = b"hello"
        self.assertProblem(entries, "outside the single top-level PPSA01234/ folder")
        flat = {name.removeprefix("PPSA01234/"): data for name, data in package_entries().items() if name != "PPSA01234/"}
        self.assertProblem(flat, "outside the single top-level")

    def test_unsafe_paths(self):
        for name in ("PPSA01234/../evil", "/PPSA01234/evil", "PPSA01234\\evil", "C:/evil", "PPSA01234//x"):
            with self.subTest(name=name):
                entries = package_entries()
                entries[name] = b"x"
                self.assertProblem(entries, "unsafe path")

    def test_symlink_rejected(self):
        write_zip(self.path, package_entries())
        with zipfile.ZipFile(self.path, "a") as archive:
            link = zipfile.ZipInfo("PPSA01234/link")
            link.create_system = 3
            link.external_attr = 0o120777 << 16
            archive.writestr(link, "/etc/passwd")
        errors = inspect_package(self.path, "PPSA01234").errors
        self.assertTrue(any("symbolic link" in e for e in errors), errors)

    def test_case_insensitive_duplicates(self):
        entries = package_entries()
        entries["PPSA01234/EBOOT.BIN"] = b"x"
        self.assertProblem(entries, "duplicates")

    def test_required_files_and_title_id(self):
        entries = package_entries()
        del entries["PPSA01234/eboot.bin"]
        self.assertProblem(entries, "missing PPSA01234/eboot.bin")
        self.assertProblem(package_entries(param_titleid="PPSA04321"), "titleId is 'PPSA04321'")
        entries = package_entries()
        entries["PPSA01234/sce_sys/param.json"] = b"{broken"
        self.assertProblem(entries, "not valid JSON")

    def test_crc_corruption_detected(self):
        entries = package_entries()
        entries["PPSA01234/assets/data.bin"] = b"A" * 4096
        write_zip(self.path, entries)
        raw = bytearray(self.path.read_bytes())
        with zipfile.ZipFile(self.path) as archive:
            info = archive.getinfo("PPSA01234/assets/data.bin")
        offset = info.header_offset + 30 + len(info.filename) + len(info.extra)
        raw[offset + 2] ^= 0xFF
        self.path.write_bytes(bytes(raw))
        errors = inspect_package(self.path, "PPSA01234").errors
        self.assertTrue(any("corrupt" in e or "size does not match" in e for e in errors), errors)


class IconTests(unittest.TestCase):
    def png(self, width, height):
        return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big")

    def test_formats(self):
        self.assertEqual(inspect_icon(self.png(512, 512)), ("png", []))
        self.assertEqual(inspect_icon(b"\xff\xd8\xff\xe0rest")[0], "jpeg")
        self.assertEqual(inspect_icon(b"RIFF\x00\x00\x00\x00WEBPVP8 ")[0], "webp")
        self.assertIsNone(inspect_icon(b"GIF89a")[0])

    def test_shape_warnings(self):
        self.assertIn("square", inspect_icon(self.png(512, 256))[1][0])
        self.assertIn("at least 256x256", inspect_icon(self.png(128, 128))[1][0])


if __name__ == "__main__":
    unittest.main()
