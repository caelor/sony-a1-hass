# Sony Control-A1 Bus

Home Assistant integration for the Sony Control-A1 (S-Link) bus. Bridges HiFi equipment (CD players, MiniDisc decks) onto a Home Assistant instance via an [ESPHome device](https://esphome.io/) attached to the physical bus, exposing media player entities, sensors, and bus diagnostics.

## Prerequisites

- **Home Assistant** with [HACS](https://hacs.xyz) installed
- An **ESP32** running the companion ESPHome component from this repository (see below). The ESP32 must be physically connected to your Control-A1 bus (3.5mm mono jack, open-collector at 5V TTL)
- Sony HiFi equipment on the Control-A1 bus (CD player address `0x90`, MiniDisc address `0xB0`, and similar)

## ESPHome component

To connect the Control-A1 bus to Home Assistant, you'll need an ESP32 running ESPHome and the bridging component found in this repository.

You will need the following sections in your ESPHome config:

```
api:
  ...
  homeassistant_services: true
  custom_services: true

external_components:
  - source: github://caelor/sony-a1-hass
    components: [ "sony_a1_bus" ]

sony_a1_bus:
  pin: 4
```

In this fragment, the Control-A1 bus is connected to GPIO4.

For simple testing, a 220R resistor can sit between the GPIO4 pin and the tip of the 3.5mm plug (this is close to pin current maximums, but can prove the communications). For a robust interface, a 2N7000 MOSFET can be used as a level shifter.


## Integration Installation via HACS

1. Ensure [HACS](https://hacs.xyz) is installed in Home Assistant.
2. Add this repository as a custom repository in HACS:
   - Go to **HACS → Integrations → ⋮ → Custom repositories**
   - URL: `https://github.com/caelor/sony-a1-hass`
   - Category: **Integration**
   - Click **Add**
3. Find **Sony Control-A1 Bus** in HACS and click **Install**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & Services → Add Integration** and search for **Sony A1 Bus** to complete setup.

## Using the integration

In general, the integration should behave intuitively.

### Logical bus device

When the integration observes events from the ESPHome devices that bridge onto the 
Sony Control-A1 bus, a bus device will be created. 

This has a sensor which tracks the last received message on that bus.

You can send an arbitrary bus message by using the `sony_a1_bus.transmit` action.
This takes a list of byte values as its data parameter, e.g.

```
action: sony_a1_bus.transmit
data:
  max_retries: 3
  device_id: your_device_id
  data:
    - 0x90
    - 0x00
```

### HiFi Equipment devices

Any Minidisc or CD Player devices that are seen on the bus should have a device 
created, creating a number of entities (including most importantly a media_player 
entity). This should appear as a child of the Logical bus device.

Buttons are created within the HiFi equipment devices to prompt a query of the
device, and to restart Table of Contents loading.

#### Metadata

External metadata lookups via MusicBrainz are provided by default (but can be
turned off per device with a config switch) and should hopefully add data such as 
titles and album art to normal CDs.

If the external lookup identifies the wrong MusicBrainz release, you can use the
`sony_a1_bus.set_musicbrainz_id` directed towards the device with the media that
you want to correct. This takes the corrected MusicBrainz ID as its parameter.

This corrected value is saved at the integration level, so if you have multiple
instances of Sony Control-A1 bus bridges, the correction should apply across all
of them.

## Documentation

- [`doc/messages.md`](doc/messages.md) — Control-A1 protocol message reference
- [`doc/low_level.md`](doc/low_level.md) — Physical bus description and timing
