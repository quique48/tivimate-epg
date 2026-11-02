import unittest
import xml.etree.ElementTree as ET
from collections import Counter

from build_layerseven_custom import (
    is_disney_plus_channel,
    is_hbo_epix_channel,
    is_max_channel,
    is_paramount_plus_channel,
    is_tudn_channel,
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

    def test_tudn_detection_excludes_xtra_event_feeds(self):
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "TUDN"
        self.assertTrue(is_tudn_channel(channel))
        from build_layerseven_custom import TUDN_ALIASES
        self.assertIn("MXC: TUDN", TUDN_ALIASES)
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "TUDN Xtra 1"
        self.assertFalse(is_tudn_channel(channel))

    def test_unlisted_public_channels_and_aliases_are_excluded(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from build_layerseven_custom import read_xml, write_custom_guide

        root = ET.Element("tv")
        tudn = ET.SubElement(root, "channel", {"id": "tudn"})
        ET.SubElement(tudn, "display-name").text = "TUDN"
        hbo = ET.SubElement(root, "channel", {"id": "hbo"})
        ET.SubElement(hbo, "display-name").text = "HBO East"
        channels = {"tudn": tudn, "hbo": hbo}

        with TemporaryDirectory() as temp_dir:
            summary = write_custom_guide(Path(temp_dir), root, channels, [], [])
            output = read_xml(Path(temp_dir) / "layerseven-custom.xml.gz")

        self.assertEqual([channel.get("id") for channel in output.findall("channel")], ["tudn"])
        names = [node.text for node in output.findall("channel/display-name")]
        self.assertIn("MXC: TUDN", names)
        self.assertNotIn("US: TUDN HD", names)
        self.assertEqual(summary["hbo_epix_channels"], 0)
        self.assertEqual(summary["tudn_aliases"], 1)

    def test_local_station_alias_has_direct_channel_and_programmes(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from build_layerseven_custom import read_xml, write_custom_guide

        root = ET.Element("tv")
        station = ET.SubElement(root, "channel", {"id": "wmaq"})
        ET.SubElement(station, "display-name").text = "WMAQ-DT"
        programme = ET.SubElement(root, "programme", {"channel": "wmaq"})
        ET.SubElement(programme, "title").text = "NBC Nightly News"
        matches = [{
            "layerseven_name": "US: NBC 5 CHICAGO IL (WMAQ) HD",
            "category": "US| NETWORK HD/4K",
            "country": "US",
            "epg_id": "wmaq",
            "epg_name": "WMAQ-DT",
            "matched_key": "WMAQ",
            "match_method": "local-station",
        }]
        matches.append(matches[0].copy())

        with TemporaryDirectory() as temp_dir:
            summary = write_custom_guide(Path(temp_dir), root, {"wmaq": station}, matches, [])
            output = read_xml(Path(temp_dir) / "layerseven-custom.xml.gz")
            nbc_output = read_xml(Path(temp_dir) / "layerseven-nbc.xml.gz")

        self.assertEqual(len(nbc_output.findall("channel")), 1)
        self.assertEqual(len(nbc_output.findall("programme")), 1)
        self.assertEqual(summary["nbc_channels"], 1)
        self.assertEqual(summary["nbc_programmes"], 1)
        direct = next(
            channel for channel in output.findall("channel")
            if channel.findtext("display-name") == "US: NBC 5 CHICAGO IL (WMAQ) HD"
        )
        self.assertNotEqual(direct.get("id"), "wmaq")
        self.assertEqual(len(direct.findall("display-name")), 1)
        direct_programmes = [
            item for item in output.findall("programme")
            if item.get("channel") == direct.get("id")
        ]
        self.assertEqual(len(direct_programmes), 1)
        self.assertEqual(direct_programmes[0].findtext("title"), "NBC Nightly News")
        self.assertEqual(summary["channels"], 2)
        self.assertEqual(summary["programmes"], 2)
        self.assertEqual(summary["direct_station_aliases"], 1)

    def test_call_sign_extraction_includes_subchannels(self):
        from build_layerseven_custom import panel_call_sign_keys

        self.assertIn("WWAYDT2", panel_call_sign_keys("US: CBS 3 (WWAY-DT2) WILMINGTON HD"))
        self.assertIn("WEVVDT2", panel_call_sign_keys("US: FOX (WEVV2) OWENSBORO HD"))
        self.assertIn("WTXFTV", panel_call_sign_keys("US: FOX WTXF TV"))
        self.assertNotIn("WEST", panel_call_sign_keys("US: NBC UNIVERSO (West)"))
        self.assertEqual(panel_call_sign_keys("US: TWINS FEED"), [])
        self.assertEqual(panel_call_sign_keys("US: DOCTOR WHO 4K"), [])
        self.assertEqual(panel_call_sign_keys("US: KING OF THE HILL 4K"), [])
        self.assertEqual(panel_call_sign_keys("US: WILL & GRACE 4K"), [])

    def test_conservative_network_name_variants(self):
        self.assertIn("NBC SPORTS BAY AREA PLUS", name_variants("US: NBC SPORTS BAY AREA PLU HD"))
        self.assertIn("GLOBAL TORONTO", name_variants("CA EN: GLOBAL NEWS TORONTO HD"))
        self.assertIn("CTV NEWS CHANNEL", name_variants("CA: CTV NEWS NETWORK"))
        self.assertIn("VIAPLAY 1", name_variants("UK: VIAPLAY SPORT 1 4K"))
        self.assertIn("NICK JR", name_variants("UK: NICK JUNIOR"))
        self.assertIn("CBC MONTREAL", name_variants("CBMT - CBC Montréal"))
        self.assertNotIn("ABC LOS ANGELES", name_variants("US: NBC LOS ANGELES"))
        self.assertNotIn("SUPER ECRAN", name_variants("CA FR: SUPER ECRAN 1 HD"))
        self.assertNotIn("NATIONAL GEOGRAPHIC", name_variants("US: NAT GEO HD"))

    def test_explicit_call_sign_overrides_generic_network_match(self):
        def public_channel(channel_id, name):
            channel = ET.Element("channel", {"id": channel_id})
            ET.SubElement(channel, "display-name").text = name
            return channel

        channels = {
            "waco": public_channel("waco", "FOX"),
            "philadelphia": public_channel("philadelphia", "WTXF-DT"),
        }
        programme_counts = Counter({"waco": 500, "philadelphia": 100})
        regions = {channel_id: {"us"} for channel_id in channels}
        inventory = [{
            "country": "US",
            "name": "US| NETWORK HD/4K",
            "channels": ["US: FOX WTXF TV"],
        }]

        matches, unmatched = match_channels(inventory, channels, programme_counts, regions)

        self.assertEqual(unmatched, [])
        self.assertEqual(matches[0]["epg_id"], "philadelphia")
        self.assertEqual(matches[0]["match_method"], "call-sign")

    def test_first_explicit_call_sign_wins(self):
        def public_channel(channel_id, name):
            channel = ET.Element("channel", {"id": channel_id})
            ET.SubElement(channel, "display-name").text = name
            return channel

        channels = {
            "nbc": public_channel("nbc", "WSVW-LD"),
            "abc": public_channel("abc", "WHSV-LD"),
        }
        programme_counts = Counter({"nbc": 89, "abc": 500})
        regions = {channel_id: {"us"} for channel_id in channels}
        inventory = [{
            "country": "US",
            "name": "US| NETWORK HD/4K",
            "channels": ["US: NBC (WSVW/WHSV) HARRISONBURG HD"],
        }]

        matches, unmatched = match_channels(inventory, channels, programme_counts, regions)

        self.assertEqual(unmatched, [])
        self.assertEqual(matches[0]["epg_id"], "nbc")
        self.assertEqual(matches[0]["matched_key"], "WSVW")

    def test_call_sign_match_preserves_exact_subchannel(self):
        def public_channel(channel_id, name):
            channel = ET.Element("channel", {"id": channel_id})
            ET.SubElement(channel, "display-name").text = name
            return channel

        channels = {
            "main": public_channel("main", "KRQE-DT"),
            "fox": public_channel("fox", "KRQE-DT2"),
        }
        programme_counts = Counter({"main": 500, "fox": 100})
        regions = {channel_id: {"us"} for channel_id in channels}
        inventory = [{
            "country": "US",
            "name": "US| FOX HD/4K",
            "channels": ["US: FOX (KRQEDT2) ALBUQUERQUE NEW MEXICO"],
        }]

        matches, unmatched = match_channels(inventory, channels, programme_counts, regions)

        self.assertEqual(unmatched, [])
        self.assertEqual(matches[0]["epg_id"], "fox")
        self.assertEqual(matches[0]["match_method"], "call-sign")

    def test_fox_sports_uses_confirmed_current_listings(self):
        def public_channel(channel_id, name):
            channel = ET.Element("channel", {"id": channel_id})
            ET.SubElement(channel, "display-name").text = name
            return channel

        channels = {
            "empty": public_channel("empty", "Fox Sports 4K"),
            "fs1": public_channel("fs1", "Fox Sports 1 US HD"),
            "fs2": public_channel("fs2", "Fox Sports 2 US HD"),
            "north": public_channel("north", "Fanduel Sports Network North HD"),
        }
        programme_counts = Counter({"empty": 0, "fs1": 109, "fs2": 109, "north": 184})
        regions = {channel_id: {"us"} for channel_id in channels}
        inventory = [{
            "country": "US",
            "name": "US| SPORT HD/4K",
            "channels": [
                "US: FOX SPORTS 1 HD",
                "US: FOX SPORTS 2 HD",
                "US: FOX SPORTS NORTH HD",
                "US: FOX SPORTS ARIZONA HD",
            ],
        }]

        matches, unmatched = match_channels(inventory, channels, programme_counts, regions)

        by_name = {match["layerseven_name"]: match for match in matches}
        self.assertEqual(by_name["US: FOX SPORTS 1 HD"]["epg_id"], "fs1")
        self.assertEqual(by_name["US: FOX SPORTS 2 HD"]["epg_id"], "fs2")
        self.assertEqual(by_name["US: FOX SPORTS NORTH HD"]["epg_id"], "north")
        self.assertTrue(all(match["match_method"] == "fox-sports" for match in matches))
        self.assertEqual([r["layerseven_name"] for r in unmatched], ["US: FOX SPORTS ARIZONA HD"])

    def test_fubo_network_uses_xumo_listing(self):
        channel = ET.Element("channel", {"id": "xumo.fuboSportsNetwork"})
        ET.SubElement(channel, "display-name").text = "Fubo Sports Network"
        inventory = [{
            "country": "US",
            "name": "US| SPORT HD/4K",
            "channels": ["US: FUBO SPORTS NETWORK HD", "US: FUBO SPORTS 1 HD"],
        }]

        matches, unmatched = match_channels(
            inventory,
            {"xumo.fuboSportsNetwork": channel},
            Counter({"xumo.fuboSportsNetwork": 80}),
            {"xumo.fuboSportsNetwork": {"us", "sports"}},
        )

        self.assertEqual(matches[0]["epg_id"], "xumo.fuboSportsNetwork")
        self.assertEqual(matches[0]["match_method"], "fubo-sports")
        self.assertEqual([r["layerseven_name"] for r in unmatched], ["US: FUBO SPORTS 1 HD"])

    def test_tsn_uses_distinct_canadian_listings(self):
        def public_channel(channel_id, name):
            channel = ET.Element("channel", {"id": channel_id})
            ET.SubElement(channel, "display-name").text = name
            return channel

        channels = {
            "tsn1": public_channel("tsn1", "TSN 1"),
            "tsn2": public_channel("tsn2", "TSN 2"),
            "tsn3": public_channel("tsn3", "TSN 3"),
        }
        programme_counts = Counter({"tsn1": 150, "tsn2": 171, "tsn3": 159})
        regions = {channel_id: {"ca"} for channel_id in channels}
        inventory = [{
            "country": "US",
            "name": "US| SPORT HD/4K",
            "channels": ["CA: TSN", "CA EN: TSN 2", "US: TSN SPORT 3 HD", "CA FR: TSN/RDS EXTRA 1"],
        }]

        matches, unmatched = match_channels(inventory, channels, programme_counts, regions)

        by_name = {match["layerseven_name"]: match for match in matches}
        self.assertEqual(by_name["CA: TSN"]["epg_id"], "tsn1")
        self.assertEqual(by_name["CA EN: TSN 2"]["epg_id"], "tsn2")
        self.assertEqual(by_name["US: TSN SPORT 3 HD"]["epg_id"], "tsn3")
        self.assertTrue(all(match["match_method"] == "tsn-sports" for match in matches))
        self.assertEqual([r["layerseven_name"] for r in unmatched], ["CA FR: TSN/RDS EXTRA 1"])

    def test_generic_sports_event_listings(self):
        from build_layerseven_custom import add_generic_event_listings

        root = ET.Element("tv")
        ET.SubElement(root, "programme", {
            "channel": "source",
            "start": "20261101000000 +0000",
            "stop": "20261103000000 +0000",
        })
        unmatched = [
            {"layerseven_name": name}
            for name in (
                "US: DAZN NFL PPV 1 - NO EVENT STREAMING -",
                "NFL  | 01 -",
                "NHL | 01 -",
                "USA Real NHL 01:",
                "NCAAF 01:",
                "NCAAB 1",
                "US (P+) UEFA Champions League 1",
                "US P+ 21 (D)",
                "US: NHL NETWORK",
            )
        ]
        output = ET.Element("tv")

        counts, programme_count = add_generic_event_listings(output, root, [], unmatched)

        self.assertEqual(counts, Counter({
            "NFL": 2, "NHL": 2, "NCAAF": 1, "NCAAB": 1, "Paramount+": 2,
        }))
        self.assertEqual(programme_count, 16)
        self.assertEqual(len(output.findall("channel")), 8)
        titles = {node.text for node in output.findall("programme/title")}
        self.assertEqual(titles, {
            "NFL Live Event", "NHL Live Event", "NCAAF Live Event", "NCAAB Live Event",
            "Paramount+ Live Event",
        })
        names = {node.text for node in output.findall("channel/display-name")}
        self.assertNotIn("US: NHL NETWORK", names)

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
