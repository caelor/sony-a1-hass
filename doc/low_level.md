# Bus Description
The HiFi equipment communicates over the Sony Control-A1 / S-Link bus.
It uses 3.5mm mono jack connectors to interconnect equipment.


# Physical Signals
The bus is a 5V TTL open-collector bus shared bus. Compatible equipment
pulls the line to idle high. When a device is transmitting, they pull the
line low.

# Signalling & Packetisation
All messages are sent in packets. Packets are formed of a sync pulse, followed
by one or more bytes of data, sent MSB first.

The sync pulse pulls the line low for 2400us, then lets the line return high for
600us.

Bits are signalled by the length of time that a line is held low - 0 bits hold the
line low for 600us, 1 bits hold the line low for 1200us. After each bit, the line
returns high for 600us as a delimiter.

At the end of a packet of data, the line returns high for at least 3000us.

# Collision Detection
As the line idles high, collisions can be detected by the line being low at unexpected
times during a transmission - e.g. during the 600us delimiter between the sync pulse
low, and the individual bit lows.