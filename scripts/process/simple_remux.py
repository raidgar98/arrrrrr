import argparse
import subprocess
import json
from typing import Any, Literal
from dataclasses import dataclass
from pathlib import Path

# Update RemuxInputs dataclass to include offsets
@dataclass
class RemuxInputs:
    audio_input: Path
    video_input: Path
    output_folder: Path
    audio_lang: str 
    sub_lang: str
    audio_title: str
    sub_title: str
    audio_track: int = 0
    subtitle_input: Path | None = None
    subtitle_track: int | None = None
    audio_offset: int | None = None  # in ms
    sub_offset: int | None = None    # in ms

    def __post_init__(self):
        path_to_validate: list[tuple[Path, str]] = [
            (self.audio_input, "Audio input"),
            (self.video_input, "Video input"),
        ]
        if self.subtitle_input:
            path_to_validate.append((self.subtitle_input, "Subtitle input"))

        # Validate input files exist
        for path, desc in path_to_validate:
            if path and not path.exists():
                raise FileNotFoundError(f"{desc} file does not exist: {path}")

    @property
    def output_file(self) -> Path:
        return self.output_folder / f"{self.video_input.stem}.mkv"

@dataclass(frozen=True)
class TrackInfo:
    index: int
    codec_name: str
    codec_type: str
    channels: int | None = None
    language: str = "und"
    tags: dict[str, str] | None = None

    def __lt__(self, other: "TrackInfo") -> bool:
        return self.index < other.index


@dataclass
class ParsedFile:
    path: Path
    id: int  # ffmpeg input index
    video_tracks: list[TrackInfo]
    audio_tracks: list[TrackInfo]
    subtitle_tracks: list[TrackInfo]

@dataclass
class TrackMapping:
    file_id: int
    track_index: int
    track_type: Literal["a", "v", "s"]  # 'video', 'audio', 'subtitle'

    def __str__(self) -> str:
        if self.track_type == "v":
            return f"{self.file_id}"
        return f"{self.file_id}:{self.track_type}:{self.track_index}"


def parse_mmss(time_str: str) -> int:
    """Convert MM:SS string into seconds (int)."""
    try:
        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    except Exception:
        raise argparse.ArgumentTypeError(f"Invalid time format '{time_str}', expected MM:SS")


def insert_silence(audio_file: Path, insert_point: str, silence_duration: float, tmp_dir: Path) -> Path:
    """Insert silence into an audio file at the given point, return new audio file path."""

    # Wykryj kodek audio
    info = run_ffprobe(audio_file)
    codec_name = next(
        (s.get("codec_name") for s in info.get("streams", []) if s.get("codec_type") == "audio"),
        "aac"
    )

    # Domyślne parametry ciszy
    codec_map = {
        "aac":  ("aac", 48000, "stereo"),
        "ac3":  ("ac3", 48000, "stereo"),
        "mp3":  ("mp3", 44100, "stereo"),
    }
    acodec, rate, channels = codec_map.get(codec_name, ("aac", 48000, "stereo"))

    # Pliki tymczasowe
    part1 = tmp_dir / "audio_part1.mka"
    part2 = tmp_dir / "audio_part2.mka"
    silence = tmp_dir / "silence.mka"
    concat_list = tmp_dir / "concat.txt"
    out_file = tmp_dir / f"{audio_file.stem}_with_silence.mka"

    # Wytnij audio przed punktem
    subprocess.run([
        "ffmpeg", "-y", "-i", str(audio_file), "-t", str(insert_point), "-c", "copy", str(part1)
    ], check=True)

    # Wytnij audio po punkcie
    subprocess.run([
        "ffmpeg", "-y", "-i", str(audio_file), "-ss", str(insert_point), "-c", "copy", str(part2)
    ], check=True)

    # Wygeneruj ciszę
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-t", str(silence_duration),
        "-i", f"anullsrc=r={rate}:cl={channels}", "-c:a", acodec, str(silence)
    ], check=True)

    # Stwórz plik concat.txt
    with open(concat_list, "w", encoding="utf-8") as f:
        f.write(f"file '{part1}'\n")
        f.write(f"file '{silence}'\n")
        f.write(f"file '{part2}'\n")

    # Sklej
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(out_file)
    ], check=True)

    return out_file



def run_ffprobe(input_file: Path) -> dict[str, Any]:
    """Run ffprobe on the input file and return parsed JSON output."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_type,codec_name,channels:stream_tags=language:format=filename",
        "-of",
        "json",
        str(input_file),
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe error: {result.stderr}")
    return json.loads(result.stdout)


def list_tracks(input_file: Path, track_type: str) -> list[TrackInfo]:
    """List tracks of a given type (audio or subtitle) in the input file."""
    info = run_ffprobe(input_file)
    tracks: list[TrackInfo] = []
    for s in info.get("streams", []):
        if s.get("codec_type") == track_type:
            tracks.append(
                TrackInfo(
                    index=int(s.get("index")) - 1,
                    codec_name=s.get("codec_name"),
                    codec_type=s.get("codec_type"),
                    channels=s.get("channels"),
                    language=s.get("tags", {}).get("language", "und"),
                    tags=s.get("tags", {}),
                )
            )
    return list(sorted(tracks))


def print_tracks(tracks: list[TrackInfo], track_type: str, input_file: Path) -> None:
    """Print available tracks of a given type."""
    print(f"\n{track_type.capitalize()} tracks in {input_file}:")
    for t in tracks:
        idx = t.index
        codec = t.codec_name
        lang = t.language
        extra = ""
        if track_type == "audio":
            extra = f", channels: {t.channels if t.channels is not None else '?'}"
        print(f"  Track {idx}: codec={codec}, lang={lang}{extra}")

def parse_file(input_file: Path, file_id: int) -> ParsedFile:
    """Parse input file and return ParsedFile with track info."""
    return ParsedFile(
        path=input_file,
        id=file_id,
        video_tracks=list_tracks(input_file, "video"),
        audio_tracks=list_tracks(input_file, "audio"),
        subtitle_tracks=list_tracks(input_file, "subtitle"),
    )

def prepare_lang_metadata(
    options: RemuxInputs,
    video: tuple[ParsedFile, TrackMapping],
    *, 
    handle_subs: bool
) -> list[str]:
    """Prepare ffmpeg arguments for language metadata and offsets."""
    args: list[str] = []

    # Audio language and offset
    new_audio_id = len(video[0].audio_tracks)
    args.extend([
        f"-metadata:s:a:{new_audio_id}", f"language={options.audio_lang}",
        f"-metadata:s:a:{new_audio_id}", f"title={options.audio_title.title()}"
    ])

    # Subtitle language and offset
    if handle_subs:
        new_sub_id = len(video[0].subtitle_tracks)
        args.extend([
            f"-metadata:s:s:{new_sub_id}", f"language={options.sub_lang}",
            f"-metadata:s:s:{new_sub_id}", f"title={options.sub_title.title()}"
        ])

    return args


def build_ffmpeg_cmd(inputs: RemuxInputs) -> list[str]:
    """Build ffmpeg command for remuxing."""

    # Parse all input files
    file_id = 0
    # Always add video input
    video_file = parse_file(inputs.video_input, file_id)

    file_id += 1
    # Add audio input if different
    audio_file = parse_file(inputs.audio_input, file_id)

    file_id += 1
    # Add subtitle input if present
    sub_file: ParsedFile | None = None 
    if inputs.subtitle_input:
        sub_file = parse_file(inputs.subtitle_input, file_id)

    # Select output tracks
    # Video: always from video_input, first video track
    out_video_track = TrackMapping(video_file.id, 1, "v")  # (file_id, track_index)
    out_audio_track = TrackMapping(audio_file.id, inputs.audio_track, "a")

    # Subtitle: optional
    out_sub_track: TrackMapping | None = None
    if sub_file is not None:
        sub_file_id = sub_file.id
        sub_track_idx = inputs.subtitle_track if inputs.subtitle_track is not None else 0
        out_sub_track = TrackMapping(sub_file_id, sub_track_idx, "s")

    # Assemble ffmpeg command
    files: list[tuple[ParsedFile | None, TrackMapping | None]] = [(video_file, out_video_track), (audio_file, out_audio_track), (sub_file, out_sub_track)]
    includes: list[str] = []
    mappings: list[str] = []
    for f, m in files:
        if f is not None:
            if inputs.audio_offset is not None and f == audio_file:
                includes.extend(["-itsoffset", str(inputs.audio_offset / 1000)])
            includes.extend(["-i", str(f.path)])
        if m is not None:
            mappings.extend(["-map", str(m)])

    cmd: list[str] = [
        "ffmpeg", 
        "-y", 
        *includes, 
        *mappings, 
        "-map_metadata", str(video_file.id), 
        "-map_chapters", str(video_file.id),
        "-c", "copy", 
        *prepare_lang_metadata(options=inputs, video=(video_file, out_video_track), handle_subs=(sub_file is not None)),
        str(inputs.output_file)
    ]

    print("FFmpeg command built successfully:", "`" + " ".join(cmd) + "`")
    print()
    return cmd

def remux(
        inputs: RemuxInputs
) -> None:
    """Perform remuxing using ffmpeg."""

    cmd = build_ffmpeg_cmd(inputs)
    print("Running ffmpeg command:")
    print(" ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError("ffmpeg remuxing failed.")
    print(f"Remuxed file saved to: {inputs.output_file}")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remux audio, video, and optional subtitles into MKV."
    )
    parser.add_argument("--audio-input", required=True, help="Path to audio input file")
    parser.add_argument("--video-input", required=True, help="Path to video input file")
    parser.add_argument(
        "--sub-input", help="Path to subtitles input file (optional)"
    )
    parser.add_argument(
        "--output-folder", default="output", help="Output folder for remuxed file"
    )
    parser.add_argument(
        "--list-tracks",
        action="store_true",
        help="list audio/subtitle tracks in inputs",
    )
    parser.add_argument(
        "--audio-track", type=int, help="Audio track index to use (default: 0)"
    )
    parser.add_argument(
        "--sub-track", type=int, help="Subtitle track index to use (default: 0)"
    )
    parser.add_argument(
        "--audio-offset", type=int, default=0, help="Audio offset in milliseconds"
    )
    parser.add_argument(
        "--sub-offset", type=int, default=0, help="Subtitle offset in milliseconds"
    )
    parser.add_argument(
        "--audio-lang", type=str, default="pol", help="Audio language (default: pol)"
    )
    parser.add_argument(
        "--sub-lang", type=str, default="pol", help="Subtitle language (default: pol)"
    )
    parser.add_argument(
        "--audio-title", type=str, default="Polish", help="Audio title (default: Polish)"
    )
    parser.add_argument(
        "--sub-title", type=str, default="Polish", help="Subtitle title (default: Polish)"
    )
    parser.add_argument(
        "--silence-point", type=str, help="Point to insert silence (in MM:SS)"
    )
    parser.add_argument(
        "--silence-duration", type=float, help="Duration of silence to insert (in seconds)"
    )

    args = parser.parse_args()

    inputs = RemuxInputs(
        audio_input=Path(args.audio_input),
        video_input=Path(args.video_input),
        output_folder=Path(args.output_folder),
        audio_track=args.audio_track if args.audio_track is not None else 0,
        subtitle_input=Path(args.sub_input) if args.sub_input else None,
        subtitle_track=args.sub_track if args.sub_track is not None else 0,
        audio_offset=int(args.audio_offset) if args.audio_offset is not None else None,
        sub_offset=int(args.sub_offset) if args.sub_offset is not None else None,
        audio_lang=args.audio_lang if args.audio_lang else "pol",
        sub_lang=args.sub_lang if args.sub_lang else "pol",
        audio_title=args.audio_title if args.audio_title else "Polish",
        sub_title=args.sub_title if args.sub_title else "Polish",
    )

    inputs.output_folder.mkdir(parents=True, exist_ok=True)

    if args.silence_point and args.silence_duration:
        silence_seconds = parse_mmss(args.silence_point)
        tmp_dir = inputs.output_folder / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        new_audio = insert_silence(inputs.audio_input, str(silence_seconds), args.silence_duration, tmp_dir)
        inputs.audio_input = new_audio

    if args.list_tracks:
        print_tracks(list_tracks(inputs.audio_input, "audio"), "audio", inputs.audio_input)
        print_tracks(list_tracks(inputs.video_input, "audio"), "audio", inputs.video_input)
        if inputs.subtitle_input:
            print_tracks(
                list_tracks(inputs.subtitle_input, "subtitle"), "subtitle", inputs.subtitle_input
            )

        print_tracks(
            list_tracks(inputs.video_input, "subtitle"), "Video::subtitle", inputs.video_input
        )
        print_tracks(
            list_tracks(inputs.audio_input, "subtitle"), "Audio::subtitle", inputs.audio_input
        )
        return

    remux(inputs)


if __name__ == "__main__":
    main()
