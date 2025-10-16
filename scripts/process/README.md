# Description and usage

## `simple_remux.py`

### Description

Simple wrapper for ffmpeg (needs to be installed and accessible). If you have two (or three) files to merge, with little shift just use proper flags:


```bash
usage: simple_remux.py [-h] --audio-input AUDIO_INPUT --video-input
                       VIDEO_INPUT [--sub-input SUB_INPUT]
                       [--output-folder OUTPUT_FOLDER] [--list-tracks]
                       [--audio-track AUDIO_TRACK] [--sub-track SUB_TRACK]
                       [--audio-offset AUDIO_OFFSET] [--sub-offset SUB_OFFSET]
                       [--audio-lang AUDIO_LANG] [--sub-lang SUB_LANG]
                       [--audio-title AUDIO_TITLE] [--sub-title SUB_TITLE]
                       [--silence-point SILENCE_POINT]
                       [--silence-duration SILENCE_DURATION]

Remux audio, video, and optional subtitles into MKV.

options:
  -h, --help            show this help message and exit
  --audio-input AUDIO_INPUT
                        Path to audio input file
  --video-input VIDEO_INPUT
                        Path to video input file
  --sub-input SUB_INPUT
                        Path to subtitles input file (optional)
  --output-folder OUTPUT_FOLDER
                        Output folder for remuxed file
  --list-tracks         list audio/subtitle tracks in inputs
  --audio-track AUDIO_TRACK
                        Audio track index to use (default: 0)
  --sub-track SUB_TRACK
                        Subtitle track index to use (default: 0)
  --audio-offset AUDIO_OFFSET
                        Audio offset in milliseconds
  --sub-offset SUB_OFFSET
                        Subtitle offset in milliseconds
  --audio-lang AUDIO_LANG
                        Audio language (default: pol)
  --sub-lang SUB_LANG   Subtitle language (default: pol)
  --audio-title AUDIO_TITLE
                        Audio title (default: Polish)
  --sub-title SUB_TITLE
                        Subtitle title (default: Polish)
  --silence-point SILENCE_POINT
                        Point to insert silence (in MM:SS)
  --silence-duration SILENCE_DURATION
                        Duration of silence to insert (in seconds)
```

### Usage

```bash

python3 simple_remux.py --video-input HD_video.mkv --audio-input SD_video_in_pl.avi --sub-input subs_in_pl.srt --output-folder out
```
