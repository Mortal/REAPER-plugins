REAPER plugins for remixing
===========================

This repository is NOT affiliated with either REAPER or LALAL.AI.

This repository implements 3rd party plugins for REAPER for creating quick remixes: running yt-dlp, stem splitting inside REAPER, beat detection, and such. It also implements a 3rd party plugin for REAPER and MuseScore for keeping playback in sync between the two programs.

For stem splitting, one plugin integrates with the API of LALAL.AI (requires a paid subscription), the other with demucs (FOSS, runs locally).

For beat detection, there is a plugin to run aubiotrack to create take markers on beats, and another plugin to set the tempo based on an item's take markers.

Requirements
------------

- REAPER 7 (tested with version 7.33)

- API key for https://www.lalal.ai/ - or a local installation of demucs

- GNU/Linux

- Python 3.10+

- gnome-terminal

- Pipewire (for plugin: Record from output monitor.py)

- Wireplumber (for plugin: auto-connect-ports.lua)

- MuseScore 4 (for plugin: Sync MuseScore 4 with REAPER.py)

- ffmpeg

- curl

- aubio (tested with version 0.4.9)


Stem splitting guide
====================

Installation
------------

- Download this repository.

- For LALAL:

  - Put your LALAL.AI API key into `~/.cache/lalalapikey`.

  - Add the script 'Split selected audio into vocals and instrumental stems with LALAL AI.py' as a custom action in REAPER.

- For demucs:

  - Add the script 'Split selected audio into vocals and instrumental stems with demucs.py' as a custom action in REAPER.

Usage
-----

1. Select a single audio media item.

2. Make a time selection of the part of the media item to split, or clear the time selection if you want to split the entire item.

3. Run the script action.


Sync with MuseScore guide
=========================

Installation
------------

- Download this repository.

- Add the script 'Sync MuseScore 4 with REAPER.py' as a custom action in REAPER.

- Copy the script 'Sync MuseScore 4 with REAPER.qml' into Documents/MuseScore4/Plugins/ (create the directory if it does not exist).

- In MuseScore, click Plugins -> Manage Plugins..., click the "Sync with REAPER" plugin and click "Activate".

Usage
-----

1. Open the REAPER project in REAPER and the associated MuseScore project in MuseScore.

2. Ensure that the "Start measure" in REAPER is set such that measure 1 on the REAPER timeline matches measure 1 in MuseScore.

3. Ensure that the MuseScore project has the same tempo set as in REAPER.

4. Activate the "Sync MuseScore 4 with REAPER.py" action in REAPER. If you run REAPER in a terminal, you should see the log message "Sync: Listening on 8085, connecting to 8084".

5. In MuseScore, go to the Plugins menu and click "Sync with REAPER". If you run MuseScore in a terminal, you should see the log messages "Sync: Listening on 8084, connecting to 8085" and "Sync: New remote connection established".

Then when you click "play" in either program, the other program should seek and start playing from the same position; when you click "pause" in either program, the other program should pause as well.
