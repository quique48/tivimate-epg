import unittest
import xml.etree.ElementTree as ET

from build_layerseven_custom import is_hbo_epix_channel, name_variants, tokens


class LayerSevenMatchingTest(unittest.TestCase):
    def test_chicago_local_normalizes_to_public_station_name(self):
        variants = name_variants("US: NBC 5 CHICAGO IL (WMAQ) HD")
        self.assertIn("NBC CHICAGO", variants)

    def test_now_prefix_is_ignored(self):
        self.assertEqual(tokens("NOW: SKY CINEMA ACTION"), ["SKY", "CINEMA", "ACTION"])

    def test_network_names_retain_gold_and_plus(self):
        self.assertIn("GOLD", name_variants("UK: GOLD 4K"))
        self.assertIn("AMC PLUS", name_variants("US: AMC PLUS HD"))

    def test_call_sign_matches_broadcast_suffix(self):
        self.assertIn("KNBC", name_variants("US: NBC 4 (KNBC) LOS ANGELES HD"))
        self.assertIn("KNBC", name_variants("KNBC-DT"))

    def test_west_direction_is_not_a_call_sign(self):
        self.assertNotIn("WEST", name_variants("US: NBC UNIVERSO (West)"))

    def test_hbo_and_epix_family_detection(self):
        for name in ("HBO East", "EPIX", "MGM+ Hits", "ScreenPix Action"):
            channel = ET.Element("channel")
            ET.SubElement(channel, "display-name").text = name
            self.assertTrue(is_hbo_epix_channel(channel))
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "PIX 11"
        self.assertFalse(is_hbo_epix_channel(channel))


if __name__ == "__main__":
    unittest.main()
