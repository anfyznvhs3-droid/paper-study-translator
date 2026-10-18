import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_privacy import scan_bytes


class NativePrivacyTests(unittest.TestCase):
    def test_detects_rust_source_in_arbitrary_build_directory(self):
        path = "Z:" + r"\builder\dependencies\serde\src\de.rs"
        self.assertTrue(scan_bytes(b"MZ\x00" + path.encode() + b"\x00"))

    def test_detects_forward_slashes_and_spaces(self):
        path = "Z:" + "/build area/registry/src/library/src/lib.rs"
        self.assertTrue(scan_bytes(path.encode()))

    def test_detects_utf16_both_alignments(self):
        path = "Z:" + r"\Users\example\project\src\lib.rs"
        for prefix in (b"", b"\x00"):
            with self.subTest(prefix=prefix):
                self.assertTrue(scan_bytes(prefix + path.encode("utf-16le")))

    def test_detects_explicit_root_without_a_rust_extension(self):
        root = "Z:" + "/private build"
        self.assertTrue(scan_bytes((root + "/generated/assets.bin").encode(), [root]))

    def test_remapped_relative_and_system_paths_are_allowed(self):
        data = ("/cargo-home/registry/src/library/src/lib.rs\0"
                "/paper-study-translator/src/main.rs\0src/lib.rs\0"
                + "C:" + r"\Windows\System32\kernel32.dll").encode()
        self.assertEqual(scan_bytes(data), [])

    def test_public_rust_source_urls_are_not_local_paths(self):
        data = b"https://example.org/project/src/lib.rs https://docs.rs/crate/latest/src/lib.rs"
        self.assertEqual(scan_bytes(data), [])


if __name__ == "__main__":
    unittest.main()
