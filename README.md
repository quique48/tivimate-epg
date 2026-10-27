# TiviMate EPG

Automatically generated XMLTV guides for the United States, Canada, the United Kingdom, and US/Canadian sports. No IPTV account credentials are used or stored.

## TiviMate URLs

For the best compatibility, start with one uncompressed regional URL. Add it under **Settings → EPG → EPG sources**, enable it for your playlist, and run **Update EPG**.

| Guide | Uncompressed XML | Compressed XMLTV.GZ |
|---|---|---|
| US national + local | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/us.xml | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/us.xml.gz |
| Chicago only | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/chicago.xml | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/chicago.xml.gz |
| Canada | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/ca.xml | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/ca.xml.gz |
| United Kingdom | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/gb.xml | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/gb.xml.gz |
| US + Canada sports | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/sports.xml | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/sports.xml.gz |
| Generic LayerSeven (US + Canada + UK + sports) | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/layerseven.xml | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/layerseven.xml.gz |
| Everything combined | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/all.xml | https://raw.githubusercontent.com/quique48/tivimate-epg/main/guides/all.xml.gz |

The combined file can be large. Regional files are recommended for Fire Sticks and other lower-memory devices. If `all.xml` exceeds the repository size threshold, only `all.xml.gz` is published.

Current generation counts and any source-fallback notices are in [guides/status.json](guides/status.json).

## Automatic updates

GitHub Actions runs every 6 hours at minute 17 (`17 */6 * * *`, UTC) and can also be started manually from the **Actions → Update XMLTV guides → Run workflow** page.

The workflow:

1. Downloads the public source guides with retries and alternative URLs where available.
2. Validates the XMLTV and merges channels/programmes while removing duplicates.
3. Reuses the last good regional output if a source is temporarily unavailable.
4. Commits updated files back to this repository.

## Sources

- EPGTalk US Lite and US Local
- EPGTalk UK Lite
- EPGTalk Sports
- epg.pw Canada, with iptv-epg.org Canada as a fallback

Coverage and schedule accuracy depend on these upstream sources. US and UK Lite guides emphasize a smaller 48-hour window; US Local, sports, and Canadian coverage can have different time windows.

## Local generation

Requires Python 3.11 or newer and no third-party packages:

```bash
python -m unittest -v
python build_guides.py --output-dir guides
```

Use the scheduling data only in accordance with upstream terms and applicable content rights.
