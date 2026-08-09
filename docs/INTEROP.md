# MilkDropper ⇄ PipeDreams interop protocol — v1

[MilkDropper](https://github.com/sworrl/MilkDropper) and
[PipeDreams](https://github.com/sworrl/pipedreams) are **sister projects**:
independent applications, separately installable, neither imports the other.
They cooperate through the small, file-and-socket contract defined here.
Both repositories ship this document; changes to the contract bump the
version at the top and must land in both repos.

## Roles

| App | Role |
|---|---|
| **MilkDropper** | Renders projectM (MilkDrop) visuals — Plasma wallpaper or standalone window — and owns the renderer processes |
| **PipeDreams** | Audio control center — device routing, EQ, spectrum analysis — and remote-controls MilkDropper's visuals |

## 1. Command channel — `/tmp/projectm-cmd`

Plain text file. **Writers** (PipeDreams, scripts, MilkDropper's own tray)
overwrite it with a single command, no trailing newline required:

| Command | Effect |
|---|---|
| `next` | Next preset |
| `prev` | Previous preset |
| `random` | Random preset |
| `lock` | Hold the current preset |
| `unlock` | Resume automatic preset cycling |
| `reload-audio` | Reconnect audio capture (after changing the source, below) |

**Readers** (every MilkDropper renderer instance — one per screen) poll at
10 Hz, deduplicate by file **mtime per instance**, and do **not** delete the
file. Writers must simply write; two writes in the same millisecond may
collapse into one command.

Shell example: `echo random > /tmp/projectm-cmd`

## 2. Audio source — `/tmp/projectm-audio-source`

Plain text file holding a PulseAudio/PipeWire **source name**
(e.g. `alsa_output.pci-0000_03_00.1.hdmi-stereo.monitor`). Empty or absent
means "monitor of the default sink".

To retarget MilkDropper's capture: write the source name, then write
`reload-audio` to the command channel. This is how PipeDreams hands its
selected capture device to the wallpaper.

## 3. Liveness & handoff — local socket `milkdropper-tray`

MilkDropper's tray listens on a `QLocalSocket` named `milkdropper-tray`
(lives in the user's runtime dir). Message-based, newline-optional:

| Message | Behaviour |
|---|---|
| `show-menu` | Pops the running tray's menu (used by a second `milkdropper` launch) |
| `ping` | Replies `milkdropper <version> mode=<off\|desktop\|standard>` then disconnects |

**Probing liveness must use `ping`** — connecting and sending nothing (or
anything else) does nothing visible. Never send `show-menu` from automation;
it opens UI in the user's face.

## 4. Detection & launching

- **Installed?** `milkdropper` / `pipedreams` on `$PATH` (also check
  `/usr/local/bin`, `/usr/bin`, `~/.local/bin`).
- **Running?** MilkDropper: `ping` on the socket (§3). PipeDreams: process
  table (`pgrep -f pipedreams`).
- **Launching:** just exec the binary, detached. MilkDropper is
  single-instance (a second launch pops the menu of the first and exits 0).
- Each app shows its sister integration **only when the sister is installed**,
  and degrades gracefully when it is not.

## Compatibility

| Contract element | Since |
|---|---|
| `/tmp/projectm-cmd`, `/tmp/projectm-audio-source` | MilkDropper 1.0.0 |
| Multi-screen mtime semantics (file not deleted) | MilkDropper 1.1.0 |
| Socket `ping` (probe-safe) | MilkDropper 1.2.0 |

Against MilkDropper 1.1.x, a `ping` pops the menu (connections were not
message-discriminated yet) — probe with `pgrep` when talking to 1.1.x.
