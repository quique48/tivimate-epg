import unittest
import xml.etree.ElementTree as ET
from collections import Counter

from build_layerseven_custom import (
    is_disney_plus_channel,
    is_hbo_epix_channel,
    is_max_channel,
    is_paramount_plus_channel,
    match_channels,
    name_variants,
    tokens,
)


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

    def test_paramount_plus_detection_excludes_paramount_network(self):
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "Paramount+ with Showtime"
        self.assertTrue(is_paramount_plus_channel(channel))
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "Paramount Network"
        self.assertFalse(is_paramount_plus_channel(channel))

    def test_disney_plus_detection_excludes_disney_channel(self):
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "Disney+CineHD"
        self.assertTrue(is_disney_plus_channel(channel))
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "Disney Channel"
        self.assertFalse(is_disney_plus_channel(channel))

    def test_max_detection_requires_exact_channel_name(self):
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "Max"
        self.assertTrue(is_max_channel(channel))
        for name in ("Sky Max", "Sony MAX", "Pop Max", "Cinemax"):
            channel = ET.Element("channel")
            ET.SubElement(channel, "display-name").text = name
            self.assertFalse(is_max_channel(channel))

    def test_cw_station_mapping_overrides_generic_match(self):
        def public_channel(channel_id, name):
            channel = ET.Element("channel", {"id": channel_id})
            ET.SubElement(channel, "display-name").text = name
            return channel

        channels = {
            "wsfl": public_channel("wsfl", "WSFL-DT"),
            "cw-miami": public_channel("cw-miami", "US - CW Miami"),
            "national": public_channel("national", "CW"),
        }
        programme_counts = Counter({"wsfl": 100, "cw-miami": 128, "national": 60})
        regions = {channel_id: {"us"} for channel_id in channels}
        inventory = [{
            "country": "US",
            "name": "US| CW HD/4K",
            "channels": ["US: CW 39 HD [MIAMI]", "US: CW NETWORK 4K"],
        }]

        matches, unmatched = match_channels(inventory, channels, programme_counts, regions)

        self.assertEqual(unmatched, [])
        by_name = {match["layerseven_name"]: match for match in matches}
        self.assertEqual(by_name["US: CW 39 HD [MIAMI]"]["epg_id"], "wsfl")
        self.assertEqual(by_name["US: CW NETWORK 4K"]["epg_id"], "national")
        self.assertTrue(all(match["match_method"] == "cw-station" for match in matches))


if __name__ == "__main__":
    unittest.main()
