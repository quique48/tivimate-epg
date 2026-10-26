import unittest
import xml.etree.ElementTree as ET

from build_guides import merge_roots


class MergeGuidesTest(unittest.TestCase):
    def test_merge_deduplicates_channels_and_programmes(self):
        first = ET.fromstring(
            """<tv>
            <channel id="one"><display-name>Channel One</display-name></channel>
            <programme channel="one" start="20261025200000 +0000" stop="20261025210000 +0000"><title>Show</title></programme>
            </tv>"""
        )
        second = ET.fromstring(
            """<tv>
            <channel id="one"><display-name>Duplicate</display-name></channel>
            <channel id="two"><display-name>Channel Two</display-name></channel>
            <programme channel="one" start="20261025200000 +0000" stop="20261025210000 +0000"><title>Duplicate</title></programme>
            <programme channel="two" start="20261025210000 +0000" stop="20261025220000 +0000"><title>Next</title></programme>
            </tv>"""
        )

        merged = merge_roots([first, second])

        self.assertEqual(len(merged.findall("channel")), 2)
        self.assertEqual(len(merged.findall("programme")), 2)
        self.assertEqual(merged.find("channel/display-name").text, "Channel One")

    def test_merge_rejects_programmes_without_channel_or_start(self):
        source = ET.fromstring(
            """<tv>
            <programme stop="20261025210000 +0000"><title>Invalid</title></programme>
            <programme channel="one" stop="20261025210000 +0000"><title>Also invalid</title></programme>
            </tv>"""
        )

        merged = merge_roots([source])

        self.assertEqual(len(merged.findall("programme")), 0)


if __name__ == "__main__":
    unittest.main()
