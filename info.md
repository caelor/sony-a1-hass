# Sony Control-A1 Bus

Home Assistant integration for the Sony Control-A1 (S-Link) bus.

## About

This integration bridges Sony HiFi equipment (CD players, MiniDisc decks) onto Home Assistant via an ESPHome device attached to the physical bus.

## Features

- Media player entities for CD players and MD recorders
- Automatic device discovery from bus traffic
- MusicBrainz metadata lookup for album art and track information
- Bus message diagnostics and monitoring
- Transmit service for sending arbitrary bus commands

## Prerequisites

- An ESP32 running the companion ESPHome component (see [README](README.md))
- Sony HiFi equipment on the Control-A1 bus (CD players, MD recorders, amplifiers, etc.)

## Documentation

See [README](README.md) for full installation and usage documentation.

## Brand Assets

Sony brand icons are sourced from the [Home Assistant brands repository](https://github.com/home-assistant/brands/tree/master/core_brands/sony) and are used in accordance with their licensing terms.