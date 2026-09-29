import unittest

from catalog.artifacts import inspect_icon


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
