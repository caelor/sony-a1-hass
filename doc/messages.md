# Packet Structure and Messages

# Other resources
https://web.archive.org/web/20070515230656/http://www.undeadscientist.com/slink/slinkcmds.html
https://web.archive.org/web/20070704164051/http://www.undeadscientist.com/slink/slinkrsps.html
https://www.boehmel.de/slink.htm


# Device Identifier
The first byte of all packets of data identifies the device.

From https://boehmel.de/slink.htm, the following information:

The device code is made up of nnnnXyyy, where:
- nnnn = device number
- X = 0 to the device, 1 from the device
- yyy = sub device number (with 111 being a broadcast to all devices)

Known device codes (nnnn) as follows:
- 0x90 - CD Player
- 0xB0 - MiniDisc Recorder
- 0xC0 - Amplifier
- 0xC1 - Tuner
- 0xC3 - Surround

# 0x90 CD Player / Changer
Commands to CD Player = 0x90, Responses from CD = x98

## Commands
Known commands (from https://web.archive.org/web/20070515230656/http://www.undeadscientist.com/slink/slinkcmds.html).
This is not an exhaustive list, some documented commands have been skipped.

- 0x00: Play
- 0x01: Stop
- 0x02: Pause
- 0x03: Pause toggle. Triggers either a 0x00 or 0x02 response as the transport state changes.
- 0x08: Next track
- 0x09: Previous track
- 0x0E: Query Disc Memory Info. Returns an 0x71 response
- 0x0F: Query status. Returns an 0x70 status message
- 0x10: Fast forward
- 0x11: Fast rewind
- 0x12: Slow Forward
- 0x13: Slow Rewind
- 0x1F: Resume/Normal
- 0x22: Query player capacity. Triggers a 0x61 message.
- 0x23: Unknown
- 0x24: Report start of track. Not universally supported, but would cause 0x09 message at start of track.
- 0x25: Verbose mode (per second 0x51 track updates, reset on playback change)
- 0x26: Brief mode
- 0x27: Query CD Text. Return 0x47 if disc has CD Text, or 0x0E if it does not
- 0x29: Unknown
- 0x2E: Power on
- 0x2F: Power off
- 0x30: Unknown
- 0x31: Unknown
- 0x32: Query artist/group mode. Returns a 0x96 message. See also commands 0x74 and 0x96
- 0x40: Query disc memo (param DD). Not universally supported. Would return 0x40 response, possibly followed by 0x80 responses
- 0x41: Query delete file (e.g. "skip tracks on this disc" list). Param DD
- 0x42: Query group memo (param GG). Returns 0x42 message.
- 0x43: Query group discs (param GG). See responses 0x43, 0x44, 0x45 and 0x78.
- 0x44: Query disc info. Param DD. Returns 0x60 if disc loaded, 0x14 if no disc
- 0x45: Query track info. Param DD TT. Returns 0x45 if track exists, otherwise 0x15
- 0x46: Query slave disc memo. Param DD. This command requests the disc memo from a slaved unit under the Megacontrol mode. Responses will be 0x46 for the first 13 bytes and 0x81 for and additional bytes.
- 0x47: Unknown
- 0x48: Query enhanced memo. Param DD. On older decks this is treated in the same way as the command 0x40. On the newer decks gets back data as 0x48 and 0x49 rather than 0x40 and 0x80 responses. Also, if the disc has CDText AND the disc is currently loaded, the full CDText is returned by the 0x48 and 0x49 messages. If not, only the memo stored in the player's memory is returned (on my CDP-CX450 this is 20 bytes).
- 0x49: Unknown
- 0x4A: BCD->Hex (older decks) / Get Track Title (newer decks). Param TT. On older decks (Control-A1 only) this changes a BCD byte to a hexadecimal byte, returned as 0x5D. On newer decks such as the CDP-CX450 the response on CD Text discs is the track name (0x4A and 0x4B), or a 0x1D if not. If passed argument of 0, returns the title of the current track.
- 0x50: Direct play. Params DD TT. 
- 0x51: Cue Track. Params DD TT
- 0x5E: Fade out. Param SS (hex value of seconds to fade out over)
- 0x5F: Fade in. Param SS (hex value of seconds to fade in over)
- 0x63: Get bar code information from disc. Param DD. Data is rarely available. Returns either 0x63 with data or 0x19.
- 0x64: Get YYYY information for current track
- 0x6A: Query deck model
- 0x72: Query deck contents.
- 0x98: Get CD Text. Param DD. If the disc is currently loaded and has CD Text, this query returns the disc name (0x48 and 0x49s) and all the track names (0x4A and 0x4Bs). If the disc is not loaded or does not have CD Text you get an 0x0E back.

## Responses
From https://web.archive.org/web/20070704164051/http://www.undeadscientist.com/slink/slinkrsps.html
Not all responses documented. Not all messages are sent by all player models.

- 0x00: Playing
- 0x01: Stopped
- 0x02: Paused
- 0x05: No disc
- 0x06: Changing discs
- 0x08: Ready. Sent "when certain commands are completed on certain CD changers"
- 0x09: Start of track. Not seen on all players.
- 0x0C: 30 seconds remaining on track.
- 0x0E: Duplicate Command / Error - Bad Arguments
- 0x0F: Error
- 0x10: No memo
- 0x11: No delete file
- 0x12: No group
- 0x13: No group
- 0x14: Disc not loaded
- 0x15: Track not available
- 0x18: Door open. Not universally sent.
- 0x19: Unknown. May be an error in response to 0x63.
- 0x1A: Unknown. May be an error in response to 0x64.
- 0x1D: No track title. May have a different meaning on old decks.
- 0x2E: Power On
- 0x2F: Power off
- 0x47: CD-TEXT Disc detected. Param 8 bytes, unknown meaning.
- 0x48: Enhanced disc memo/CDText. Response to 0x48 command. Param DD u1 b1 CCx14. u1 is unknown, b1 is: 0x00=Memo, 0x03=CDText, 0x07=CDText - although CDText has been observed with 0x00.
- 0x49: Enhanced disc memo continued. Follows the 0x48 response. Param BB CCx16.
- 0x4A: CD Text Track name. Param TT u1 b1 CCx14. u1 and b1 match the 0x48 values.
- 0x4B: CD Text track continuation. Param BB CCx16.
- 0x50: Playing disc. Param DD TT MM SS
- 0x51: Time update message. Param TT II MM SS. II is track index. Very rarely used, but subdivides tracks.
- 0x52: Displaying Disc (on front panel). Param DD
- 0x53: Missing disc. Param DD
- 0x54: Loading disc. Param DD
- 0x55: Disc has no memo. Param DD
- 0x58: Loaded disc. Param DD
- 0x5D: BCD to Hex response. Param HH
- 0x60: Disc info. Param DD II TT MM SS FF. II=Indexes, FF=frames
- 0x61: Deck size. Param DD ZZ. ZZ is a capabilities byte.
- 0x62: Queried track. Response to 0x45. Param DD TT MM SS
- 0x63: Disc Bar Code. Param DD CCx7. Response to 0x63 command.
- 0x64: YYYY track info. Param TT CCx8. Response to 0x64 sometimes.
- 0x6A: Deck Model. Param CCx?. Response to 0x6A command.
- 0x70: Status message. Param S1 S2 S3 DD TT.
- 0x71: Disc Memory information. Param SS. Bit 0x01 set=memo/title set, Bit 0x02 set=delete file set, Bit 0x30 set=CD Text. Other 5 bits only observed to be 0.
- 0x80: Disc memo continued. Param DD LL CCx?. Possible following the 0x40 response. Continues if data is >13 bytes returned by 0x40.
- 0x81: Slave disc memo continued. Param DD LL CCx?. Possible following 0x46 response. Continues if data is 13 character returned by 0x46.
- 0x83: Door closed.
- 0x92: Artist name. Param AA PP CCx13. AA=artist, PP=packet num.
- 0x93: Artist not set. Param AA.
- 0x96: Artist/Group mode. Param GG AA GGmax AAmax. Response to command 0x32, 0x74 or 0x96. If in group mode, [group] is the group number. Likewise if in artist mode, [artist] is the artist being played. If both [group] and [artist] are zero then not in either mode.


### Status Message decode notes
*Note: This information is taken from the undeadscientist CD-changer protocol decode - more recent reverse engineering has better information about S1*
 The first byte indicates the player status:
0x00 = Player On, Stopped
0x01 = Player On, Playing
0x02 = Player On, Paused
0x03 = Door Is Open 0x10 = Player Off
0x2F = No Discs in Player, Power On
0x3F = No Discs in Player, Power Off

This is clearly bit packed data, but all of the details of which bits represent which conditions haven't been puzzled out. Bit 2 is suspected to be a player empty flag, and bit 3 a power off flag, bits 6 & 7 appear to code playback states.

No other values have been observed, but thanks to everyone who has paid attention to how the messages change.

The second byte contains the following information:
bit 0 (most significant bit):
0 = scanning discs, 1 = discs known
bit 1:
0 = single disc mode, 1 = all disc mode
bits 2-3:
00 = repeat off, 01 = repeat all, 10 = repeat one
bits 4-7:
0000 = no program, not shuffle
0001 = shuffle
0100 = program one
0101 = program two
0110 = program three
Note that just checking bit 7 will confuse program two and shuffle

The meaning of the third byte isn't clear - it may be reserved for later features, it seems to always be 0x00.

The fourth byte is the disc currently loaded.

The fifth byte is the track number (if paused or playing) or 0x00 (if stopped).



# 0xB0 MiniDisc
Commands to MiniDisc = 0xB0, Responses from MiniDisc = 0xB8.

## Commands
Known commands as follows (curated from https://boehmel.de/slink.htm):

- 0x00: Play
- 0x01: Stop
- 0x02: Pause
- 0x03: Pause toggle
- 0x04: Eject
- 0x07: Record pause (receives answer 0x07)
- 0x08: skip +
- 0x09: skip -
- 0x10: ffw fast (end with play or normal)
- 0x11: rew fast (end with play or normal)
- 0x12: ffw slow (end with play or normal)
- 0x13: rew slow (end with play or normal)
- 0x1F: normal (ends slow/fast ffw/rew)
- 0x22: device type (receives answer 0x61)
- 0x25: time update on (received 0x51 every second until end of track)
- 0x26: time update off
- 0x2E: Power on
- 0x2F: Power off
- 0x44: Query Disk. Parameters: DD (1 byte, disc number - see 0x61 disc capacity message). Receives answer 0x60 disc info
- 0x45: Query Track. Parameters: DD (1 byte, disc number - see 0x61 disc capacity message), TT (1 byte, track num - see 0x60 disc info message). Receives answer 0x62 track info
- 0x50: Play direct track. Parameters: DD (1 byte, disc number - see 0x61 disc capacity message), TT (1 byte, track num - see 0x60 disc info message)
- 0x54: Remain Time Disc
- 0x58: Query Disc Name. Parameters: DD (1 byte, disc number - see 0x61 disc capacity message) 0x00
- 0x5A: Query Track Name: Parameters: TT (1 byte, track number) 0x00
- 0x6A: Device name. Receives answer 0x6A
- 0x98: Write Disk Text. Parameters: DD (1 byte, disc number - see 0x61 disc capacity message) 0x00 0x00 CC (14 bytes, pad with 0x00). Receives answer 0x1F on ok
- 0x99: Write Disk more text. Parameters: BB (1 byte - block number >1), CC (16 bytes, pad with 0x00). Receives answer 0x1F on ok
- 0x9A: Write Track text. Parameters: TT (1 byte, track num - see 0x60 msg) 0x00 0x00 CC (14 bytes, pad with 0x00). Receives answer 0x1F on ok
- 0x8B: Write Track more text. Parameters: BB (1 byte - block number >1), CC (16 bytes, pad with 00). Receives answer 0x1F on ok.

CC characters are ascii 0x20 - 0x5A, japanese 0xA6-0xAF and 0xB1 - 0xDF


## Responses
Known messages from MD player (and possibly other players in some cases):

- 0x00: Play
- 0x01: Stop
- 0x02: Pause
- 0x03: TOC Updated - Triggers TOC query sequence in the bridge (also used on eject)
- 0x04: Record Play
- 0x05: Ignored
- 0x06: Seeking (CD Player - unloading or moving carousel)
- 0x07: Record Pause
- 0x08: Ready
- 0x09: Start of track
- 0x0C: 30sec to end of track
- 0x0E: Unavailable
- 0x0F: Error
- 0x10: No Memo
- 0x11: No delete File
- 0x12: No group
- 0x14: Invalid disk number (used in disc info query). Bridge aborts TOC query on this response.
- 0x15: Invalid disk or track number (used in track info query)
- 0x16: No disc name on disc. Bridge uses "No name" placeholder.
- 0x17: No track name on disc. Bridge uses "No name" placeholder and advances TOC state.
- 0x18: Door open (only CD-Changer)
- 0x19: No group (only CD-Changer)
- 0x1D: No CD Text
- 0x1F: Title written to memory
- 0x2E: Power on
- 0x2F: Power off
- 0x31: ??? (Answer to command 0x42)
- 0x33: Complete
- 0x50: Track Status. Parameters: DD (1 byte disc num) TT (1 byte track num) MM (1 byte minutes BCD) SS (1 byte seconds BCD)
- 0x51: Time Update status. Sent in response to command 0x25. Parameters differ by device type: on CD, TT (1 byte track BCD) II (1 byte sub-track index) MM (1 byte minutes BCD) SS (1 byte seconds BCD) — CD carries no disc number; on MD, TT (1 byte track num) DD (1 byte disc num) MM (1 byte minutes BCD) SS (1 byte seconds BCD).
- 0x54: Time remain disc. Parameters: DD (1 byte disc num) MM (1 byte minutes BCD) SS (1 byte seconds BCD)
- 0x58: Disc text first block. Parameters: DD (1 byte disc num) 0x00 0x00 CC (14 bytes 0x00 padded)
- 0x59: Disc text continuation block. Parameters: BB (1 byte block >1) CC (16 bytes 0x00 padded)
- 0x5A: Track text first block. Parameters: TT (1 byte track num) 0x00 0x00 CC (14 bytes 0x00 padded)
- 0x5B: Track text continuation block: Parameters: BB (1 byte block >1) CC (16 bytes 0x00 padded)
- 0x60: Disc info: Parameters: 0x01 0x01 TT (1 byte track count; BCD on CD, hex on MD) MM (1 byte minutes BCD) SS (1 byte seconds BCD) 00.
- 0x61: Disc capacity, model identifier. Parameters: DD (1 byte discs count) ID (1 byte device id)
- 0x62: Track info. Parameters: DD (1 byte disc id) TT (1 byte track id) MM (1 byte minutes BCD) SS (1 byte seconds BCD)
- 0x6A: Device name. Parameters: CC (17 bytes, 0x00 padded). Responds to 0x6A command.
- 0x70: Status. Parameters: S1 (1 byte) S2 (1 byte) S3 (1 byte) DD (1 byte disc num) TT (1 byte track num)
- 0x71: After TOC read, inserting disc. Sets transport_state to "loading". Parameters: 0x00 0x01 0x00 0x00 0x00 OR 0x00 0x01 0x00 0x01 0x00

Status byte values:
- S1: 00=Stop, 01=Play, 02=Pause, 04=Rec, 05=Rec-Pause
- S2: bit 0=shuffle; bit1=program; bit2=0=one_disc,1=all_discs (CD only - omitted for MD since all known MD decks are single-disc); bit3=repeat_all; bit4=repeat1; bit5=writable (while playing); bit6=???; bit7=???
- S3: bit2..bit0=input, bit7=mono

Input bitmask:
- 000=analog
- 011=optical
- 101=coax


# Universal Messages

The following messages are assumed to work across all device types (CD, MD, AMP, Tuner, Surround). The bridge handles these in a universal message handler before dispatching to type-specific decoders.

**Empirically confirmed:**
- 0x2E: Power on (response)
- 0x2F: Power off (response)
- 0x70/0x71: Status (response)
- 0x6A: Device name query (command) and response

**Assumed universal (based on protocol similarity):**
- 0x00-0x07: Transport state (play, stop, pause, record, record_pause, seeking)
- 0x6A: Device name query

The universal message handler tracks power state transitions and emits POWER_ON/POWER_OFF events only on actual transitions (false→true, true→false) to prevent duplicate events when a device sends 0x2E/0x2F multiple times during boot.


Known Device IDs:
- 0x07: MDS-JE530



# Model Identifiers
These are the known values of the ID field from the `0x61` message:

| Value | Model |
| ----- | ----- | 
| 0x07  | MDS-JE530 Minidisc |
| 0x0B  | Unknown CD (reported by https://boehmel.de/slink.htm) |
| 0x20  | CDP-XE520 CD Player |



# Known Messages
This is not a full exhaustive list, but is an attempt to map the similarities and consistencies of the message set between CD and MD devices.

## Command Messages
The following are the known messages sent TO the equipment

| Cmd Byte | CD | MD | Params | Description & Notes |
| -------- | -- | -- | ------ | ------------------- |
|  0x00    | x  | x  |        | Play - for soft-off devices will power on the device to play |
|  0x01    | x  | x  |        | Stop |
|  0x02    | x  | x  |        | Pause |
|  0x03    | x  | x  |        | Pause Toggle |
|  0x04    | x  | x  |        | Eject |
|  0x07    |    | x  |        | Record Pause |
|  0x08    | x  | x  |        | Skip+ |
|  0x09    | x  | x  |        | Skip-
|  0x0E    | x  | x  |        | Query stored - asks if a disc is loaded. Triggers an 0x71 response if it is |
|  0x0F    | x  | x  |        | Setup info. Triggers a 0x70 status response. Can be used for status polling |
|  0x10    | x  | x  |        | Fwd Fast |
|  0x11    | x  | x  |        | Rew Fast |
|  0x12    | x  | x  |        | Fwd Slow |
|  0x13    | x  | x  |        | Rew Slow |
|  0x1F    | x  | x  |        | Normal Speed |
|  0x22    | x  | x  |        | Query device type. Triggers a 0x61 response |
|  0x25    | x  | x  |        | Time update on. Sends 0x51 message every second until the end of the track |
|  0x26    | a  | a  |        | Time update off. |
|  0x2E    | x  | x  |        | Power on |
|  0x2F    | s  | s  |        | Power off. Triggers a 0x0F response from a hard power device, or a 0x2F response on success (soft power device) |
|  0x32    | a  | a  |        | CD: Query artist/group mode; MD: Divide |
|  0x33    |    | a  |        | Menu yes |
|  0x34    |    | a  |        | Menu no |
|  0x35    |    | a  |        | Undo |
|  0x3E    | a  | a  |        | Disable device keys |
|  0x3F    | a  | a  |        | Enable device keys |
|  0x40    | a  | a  | TT     | CD: Query disc memo; MD: Erase track TT (without confirmation) |
|  0x41    | a  | a  | T1 T2  | CD: Query delete file; MD: Move track T1 to T2 (without confirmation) |
|  0x42    | a  | a  | TT     | CD: Query group memo; MD: Combine track TT with previous track |
|  0x43    | a  | a  | TT     | CD: Query group discs; MD: Combine with track TT (without confirmation) |
|  0x44    | x  | x  | DD     | Query disc. Prompts a 0x60 response (or 0x14 with no disc). Valid DD between 01 and DD value given in 0x61 message inclusive (most likely 01 only) |
|  0x45    | x  | x  | DD TT  | Query track. Prompts a 0x62 response (or 0x15 for invalid track). Valid DD is 01 to value given by 0x61 message. Valid TT is 01 to value given by 0x60 message. For CD this appears to be BCD encoded, for MD it's not BCD. |
|  0x46    | a  | a  |        | CD: Query slave disc memo; MD: Split adjust |
|  0x48    | x  |    | DD     | Query enhanced memo. Triggers 0x48 and 0x49 responses, returning CD Text if available. |
|  0x4A    | x  |    | TT     | Query Track title (newer players only). Triggers 0x4A and 0x4B for track title, 0x1D if data not available. |
|  0x50    | x  | x  | DD TT  | Play direct track |
|  0x51    | x  | x  | DD TT  | Cue direct track (cue and pause) |
|  0x54    | ?  | ?  | DD     | Remaining time disc |
|  0x58    | ?  | x  | DD 00  | Query disc name. Triggers 0x16 response |
|  0x5A    | ?  | x  | TT 00  | Query track name. Triggers 0x17 response |
|  0x63    | a  | ?  | DD     | Get disc bar code information. Triggers 0x63 or 0x19 |
|  0x64    | a  | ?  |        | Get YYYY info of current track. Triggers ??? |
|  0x6A    | x  | x  |        | Query device name. Triggers 0x6A response |
|  0x72    | ?  | ?  | TT     | CD: Query deck contents; MD: Record date. Needs investigation. May trigger a 0x72 response |
|  0x76    |    | a  | DD TT  | Combine track a+b |
|  0x78    |    | a  |        | a-b erase, set point a |
|  0x79    |    | a  |        | a-b erase, set point b |
|  0x7A    |    | a  |        | adjust point a |
|  0x7B    |    | a  |        | adjust point b |
|  0x7C    |    | a  |        | a-b erase, confirm point a |
|  0x7D    |    | a  |        | confirm a-b erase |
|  0x97    | ?  | ?  | 01 00  | Disc info |
|  0x98    | x  |    | DD     | Get CD Text. Triggers a dump of 0x48/0x49 messages for Disc name, and 0x4A/0x4B for track titles. If there's no disc or no CD-TEXt then 0x0E is returned |
|  0x98    |    | ?  | DD 00 00 CCx14 | Write disc text. Initial block. Valid DD is between 01 and DD value given in 0x61 message. CC is exactly 14 bytes, 0x00 padded if needed. Generates 0x1F on success. |
|  0x99    |    | ?  | BB CCx16 | Write disc more text. Follow on block. BB is block number, >01 (BB==01 is sent with 0x98). CC is exactly 16 bytes, 0x00 padded if needed. Generates 0x1F on success. |
|  0x9A    |    | ?  | TT 00 00 CCx14 | Write track text. Initial block. Valid TT is between 01 and TT value given in 0x60 message. CC is exactly 14 bytes, 0x00 padded if needed. Generates 0x1F on success. |
|  0x9B    |    | ?  | BB CCx16 | Write track more text. Follow on block. BB is block number, >01 (BB==01 is sent with 0x98). CC is exactly 16 bytes, 0x00 padded if needed. Generates 0x1F on success. |

Key for CD and MD columns:
- x: Confirmed (or implicitly expected as universal)
- ?: Needs testing
- a: Assumed (documented, but not yet used)
- s: Soft on/off devices only.
- blank: Not available / Not expected (may be present but not tested/confirmed)


## Response Messages 
The following are known messages sent FROM the equipment

| Cmd Byte | CD | MD | Params | Description & Notes |
| -------- | -- | -- | ------ | ------------------- |
|  0x00    | x  | x  |        | Device has started playing |
|  0x01    | x  | x  |        | Device has stopped playing |
|  0x02    | x  | x  |        | Device has paused |
|  0x03    | x  | x  |        | TOC Updated. Observed after eject on CD & MD |
|  0x04    |    | x  |        | Device has entered record-play |
|  0x05    | ?  | ?  |        | CD: No disc; MD: Ignored (unclear when this is sent) |
|  0x06    | ?  | ?  |        | Seeking/Changing Discs. May only be sent if a CD changer is moving carousel |
|  0x07    |    | x  |        | Device has entered record-pause |
|  0x08    | x  | x  |        | Device indicates it is ready. Observed after: Disc Load, ... |
|  0x09    | ?  | ?  |        | Device is at start of track |
|  0x0C    | x  | x  |        | Sent 30s before the end of the playing track |
|  0x0E    | x  | x  |        | Bad Arguments / Unavailable (unclear when this is sent) |
|  0x0F    | x  | x  |        | Error response to a previous message. Sent in response to some invalid messages (e.g. 0x70 sent to device) |
|  0x10    | x  | ?  |        | No memo |
|  0x11    | x  | ?  |        | No delete file |
|  0x12    | x  | ?  |        | No group |
|  0x14    | x  | x  |        | Invalid disc #, possibly sent in response to 0x44 command |
|  0x15    | x  | x  |        | Invalid disc or track #, possibly sent in response to 0x45 command |
|  0x16    | ?  | ?  |        | No disc name on disc |
|  0x17    | ?  | ?  |        | No track name on disc |
|  0x18    | a  |    |        | Door open. CD Changer only |
|  0x19    | a  |    |        | No group. CD Changer only |
|  0x1D    | ?  |    |        | No CD Text |
|  0x1F    |    | ?  |        | Title written to memory. Sent in response to 0x98-0x9B commands. |
|  0x2E    | x  | x  |        | Power on. Sent by both soft and hard power devices when powered up and active. |
|  0x2F    | ?  | x  |        | Power off. Sent only by soft power devices when moving to soft power-off mode. |
|  0x31    |    | a  |        | Unknown. Documented as in response to 0x42 combine command |
|  0x33    | ?  | ?  |        | Complete |
|  0x47    | x  |    | ???    | CD Text Detected. Observed 47 09 09 FF FF FF FF FF FF FF on a CD Text disc on load. Apparently 47 09 09 00 00 00 00 00 00 00 has also been seen. |
|  0x48    | x  |    | DD u1 b1 CCx14 | Enhanced Disc memo/CD Text initial block. Sent in response to 0x48 command. b1=0x00 is memo, 0x03 or 0x07 is CD Text. |
|  0x49    | x  |    | BB CCx16 | Enhanced Disc memo/CD Text continuation. BB is block number |
|  0x4A    | x  |    | TT u1 b1 CCx14 | CD Text track info initial block. Sent in response to 0x4A command |
|  0x4B    | x  |    | BB CCx16 | CD Text track data continuation. BB is block number |
|  0x50    | ?  | x  | DD TT MM SS | Track status. DD=disc, TT=track, MM=minutes, SS=seconds. All are documented as BCD encoded |
|  0x51    | ?  | x  | TT II/DD MM SS | Time update status. Sent in response to command 0x25. On CD: TT=track, II=sub-track index (no disc number). On MD: TT=track, DD=disc. MM=minutes, SS=seconds, BCD encoded. |
|  0x52    | x  | ?  | DD     | Displaying "disc DD" on the front panel | 
|  0x53    | x  |    | DD     | Missing disc. |
|  0x54    | x  |    | DD     | Loading disc |
|  0x54    |    | x  | DD MM SS | Remaining time disc. DD=disc, MM=minutes, SS=seconds. All BCD encoded. Upper nibble of MM may not be truly BCD as 100min=0xa0. For min>255, value is "wrong value" as per docs |
|  0x55    | x  |    | DD     | Disc has no memo. |
|  0x58    | x  |    | DD     | Loaded disc |
|  0x58    | ?  | x  | DD 00 00 CCx14 | Disc text. First block of disc text, CC exactly 14 bytes character string, 0x00 padded if needed. A "0x58 0x01" variant has also been observed from a CD player (with no CD text) |
|  0x59    |    | x  | BB CCx16 | Disc more text. Second and onward blocks of disc text, CC exactly 16 bytes character string, 0x00 padded if needed. |
|  0x5A    |    | x  | TT 00 00 CCx14 | Track text. First block of track text, CC exactly 14 bytes character string, 0x00 padded if needed. |
|  0x5B    |    | x  | BB CCx16 | Track more text. Second and onward blocks of track text, CC exactly 16 bytes character string, 0x00 padded if needed. |
|  0x60    | x  | x  | DD II TT MM SS FF | Disc info. DD=Disc, II=Indexes, TT=number of track (BCD on CD, hex on MD), MM=total playing minutes (BCD), SS=total playing seconds (BCD), FF=Frames (00 on MD). Sent in response to 0x44 command. |
|  0x61    | x  | x  | DD ID  | Disc capacity & device ID. Sent unsolicited on power on, and in response to 0x22 command. ID may instead be a bitmask indicating capability, rather than identifying a specific model |
|  0x62    | x  | x  | DD TT MM SS | Track info (playing time). DD=disc (assumed hex), TT=track (hex), MM=minutes (BCD), SS=seconds (BCD). Sent in response to 0x45 command. |
|  0x63    | x  | ?  | DD CCx7 | Disc bar code. Sent in response to 0x63 command |
|  0x64    | x  | ?  | TT CCx8 | YYYY track info. Sent in response to 0x64. |
|  0x6A    | x  | x  | CCx17  | Device name. 0x00 padded string, 17 bytes long. Sent in response to 0x6A command. |
|  0x70    | x  | x  | S1 S2 S3 DD TT | Device Status. See below for S1, S2 and S3 values. DD=disc number, TT=track number. Sent in response to 0x0F and potentially unsolicited. |
|  0x71    | x  |    | SS     | Disc memory information. In SS, bit 0x01 is memo/title set, bit 0x02 is delete file set, bit 0x30 is CD text set. Other bits observed to be 0. |
|  0x71    |    | x  | u1 u2 u3 u4 u5 | Observed after TOC read, inserting disc. Parameters unknown. Sent in response to 0x0E. Only appears to be sent if a Disc is inserted. Possibly u1 maps to the CD version. |




BCD encoding of numbers appears to be (upper nibble of data * 10) + (lower nibble of data)
e.g. res = 10 * (data >> 4) + (0x0F & data);


### Status byte S1 (from 0x70 response)
The S1 byte provides information about the transport status.

This is confirmed to be a bitmask flag with the following values:

| Bit | Flag |
| --- | ---- |
|  0  | Transport b0 |
|  1  | Transport b1 |
|  2  | Transport b2 |
|  3  | Unknown |
|  4  | Power on = 0, off = 1 |
|  5  | Disc Loaded = 0, Unloaded = 1 |
|  6  | Unknown |
|  7  | Unknown |

Transport status:
- 000 = Stopped
- 001 = Playing
- 010 = Paused
- 100 = Recording
- 101 = Recording pause

Seen absolute values:
- 0x00 - on, disc inserted, stopped
- 0x01 - on, disc inserted, playing
- 0x02 - on, disc inserted, paused
- 0x05 - on, disc inserted, record paused
- 0x10 - off, disc inserted
- 0x23 - on, no disc
- 0x33 - off, no disc

0x04 is also assumed for recording.

These values are similar BUT DISTINCT from the standalone transport response codes.


### Status byte S2 (from 0x70 response)
The S2 byte provides information about playlists and writability:

| Bit | Status |
| --- | ------ |
|  0  | Shuffle flag |
|  1  | Program flag |
|  2  | 0=one disc, 1=all discs. Likely CD Changer only |
|  3  | Repeat-all flag |
|  4  | Repeat-one flag |
|  5  | writable flag (while playing) |
|  6  | Unknown |
|  7  | Unknown |

### Status byte S3 (from 0x70 response)
The S3 byte provides information about device configuration (primarily relating to recording). 
It is suspected that S3 always is 0x00 for CD players.

Bits 2..0 describe the selected recording input:

| Bits 2..0 | Input Source |
| 001 | Analog |
| 011 | Optical |
| 101 | Coax |

Bit 7 of S3 is a flag indicating mono mode on or off.
