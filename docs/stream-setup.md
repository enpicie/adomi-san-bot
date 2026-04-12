---
layout: default
title: Stream Setup
---

# Stream Setup

Open Broadcaster Software (**OBS**) is an app commonly used for streaming and NEST supports a set of OBS scenes to help you get a stream set up. 

- [Download OBS](https://obsproject.com/download).
- [Download Netplay Tournament Scenes](/nest/assets/Netplay_Tournament_Scenes.json)


This set of Netplay Tournament Scenes comes with the following:
- Starting Soon scene with BGM and background image
- 4:3 windowed game setup to stream games like MBAACC or other non-Steam games
- 16:9 game setup to stream games available on Steam or other 16:9 ratio games

> When importing, ignore any warnings of missing files as you will need to set these yourself with your own files.

## Prerequisites

[Application Audio Capture Plugin](https://obsproject.com/kb/application-audio-capture-guide) - This is needed for capturing audio from Discord or the games

[fgc-scoreboard with customization tool](https://github.com/chzylee/fgc-scoreboard-customizations/releases/tag/v1.0.0) - This is an easy scoreboard to setup and comes with settings in StreamControl to customize colors of the scoreboard and show/hide a logo at the bottom.

> Extract the files in the .zip download and open `StreamControl.exe` in the sc directory to launch the application used to control the scoreboard.

Special thanks to Tarik of WASD Gaming as it builds on the [original fgc-scoreboard](https://github.com/WASD-Gaming/fgc-scoreboard).

## Scene Configuration

Many sources in the OBS scenes can be configured for you to personalize your setup.

| Source | Description |
| --- | --- |
| `Comms VC Overlay` | Link to [Discord overlay widget](https://streamkit.discord.com/overlay) to show commentators in a Discord Voice channel to show who is commentating |
| `Chat` | Use [StreamElements](https://streamelements.com/) or another tool to setup chat visibility on your stream |
| `FGC Scoreboard` | Point to local file `_overlays/scoreboard.hml` from the fgc-scoreboard files extracted from [Prerequisites](#prerequisites) download |
| `Discord Audio` | Set this to capture audio from your Discord window to capture audio from commentary |
| `Starting Soon BGM` | You can make a .xspf playlist in VLC or similar software and it will play the playlist as scene BGM |

`Game Capture` and `Game Window Capture` should be used to capture each game. `Game Audio` and `Windowed Game Audio` can also be used to capture audio from respective games.

## Recommendations

For a smoother commentary experience, it is recommended to run games *windowed* while using the appropriate game capture. Normal `Game Capture` is still compatible with Steam games running in windowed mode. Screenshots below show what I setup on the screen I share with commentators when running netplay events.

### 4:3 Game Example (MBAACC)
![4:3 Game Screen Stream Example](./assets/43%20stream%20example.png)

### 16:9 Game Example (UNI2)
![16:9 Game Screen Stream Example](./assets/169%20stream%20example.png)