from __future__ import annotations
import contextlib
from typing import Literal, get_args
from pymediainfo import MediaInfo, Track
from pathlib import Path
from argparse import ArgumentParser
from dataclasses import dataclass


TEST_PATH = Path("/storage/disk/B/Vikings.S01.MULTi.1080p.NF.WEB-DL.DDP5.1.H.264.PACK-PSiG/Vikings.S01E01.Rites.of.Passage.MULTi.1080p.NF.WEB-DL.DDP5.1.H.264-PSiG.mkv")

MediaTypeT = Literal["series", "season", "episode", "movie"]
RipTypeT = Literal["WEBRip", "WEB-DL", "Encode", "Remux", "DVDRip", "BRRip", "BluRay"]
VideoCodecT = Literal["x264", "x265"] | str
AudioCodecT = Literal["EAC3", "AAC2", "AAC"] | str

# mi = MediaInfo.parse(TEST_PATH)
# pass

@dataclass(kw_only=True)
class Arguments:
    # FILE
    path: Path

    # INFO
    media_type: MediaTypeT
    name: str
    episode: int | None = None
    seasons: list[int] | None = None
    year: int | None = None

    # SOURCE
    group: str = "PTTrG"
    rip_source: str | None = None
    rip_type: RipTypeT = "WEB-DL"

    # VIDEO
    video_codec: VideoCodecT | None = None
    audio_codec: AudioCodecT | None = None

    def __post_init__(self) -> None:
        if self.media_type is None:
            if self.episode is None and self.seasons is None and self.year is not None:
                self.media_type = "movie"
            elif self.episode is not None and self.seasons is not None and len(self.seasons) == 1:
                self.media_type = "episode"
            elif self.episode is None and self.seasons is not None and len(self.seasons) == 1:
                self.media_type = "season"
            elif self.episode is None and self.seasons is not None and len(self.seasons) > 1:
                self.media_type = "series"
        assert self.media_type in get_args(MediaTypeT), "Media type is not set or is not supported"

@dataclass
class VideoInfo:
    resolution: int
    codec: VideoCodecT

def parse_series_num(incoming: list[str] | str) -> list[int]:
    if incoming is None or len(incoming) == 0:
        return []
    if isinstance(incoming, list) and len(incoming) > 1:
        return [int(x) for x in incoming]
    
    incoming = incoming[0]
    with contextlib.suppress(ValueError):
        return [int(incoming)]

    for sep in (":", "-"):
        if sep in incoming:
            start, end = incoming.split(sep)
            return [x for x in range(int(start), int(end) + 1)]
    raise SyntaxError("Invalid format of series. Expected `-s 1 2 3` or `-s 1:3` or `-s 1-3`")

def parse_arguments() -> Arguments:
    # return Arguments(
    #     path=Path("/storage/disk/B/Vikings.S01.MULTi.1080p.NF.WEB-DL.DDP5.1.H.264.PACK-PSiG/Vikings.S01E01.Rites.of.Passage.MULTi.1080p.NF.WEB-DL.DDP5.1.H.264-PSiG.mkv"),
    #     name="Vikings",
    #     seasons=[1, 2],
    #     media_type="series"
    # )

    defaults = Arguments(path=Path(), name="", media_type="movie")
    args = ArgumentParser("mktorrentname")
    args.add_argument("path", type=Path, help="Path to exact file (regardless if movie/series)")
    args.add_argument("-m", "--media-type", dest="media_type", type=str, required=False, choices=get_args(MediaTypeT))
    args.add_argument("-n", "--name", dest="name", type=str, help="Name of the show/movie")
    args.add_argument("-y", "--year", dest="year", type=int, required=False, help="Year of first series emission or movie release")
    args.add_argument("-e", "--episode", dest="episode", type=int, required=False, help="Episode number (works only for episode media type)")
    args.add_argument("-s", "--seasons", dest="seasons", type=str, nargs="*", required=False, help="Seasons number, can be one (for season media pack) or multiple (for series media type). Can be provided as: `-s 1 2 3` or `-s 1-3` or `-s 1:3`")
    args.add_argument("-g", "--group", dest="group", type=str, default=defaults.group, help="Name of group that RIPped file")
    args.add_argument("-r", "--rip-type", dest="rip_type", type=str, default=defaults.rip_type, choices=get_args(RipTypeT), help="RIP Type")
    args.add_argument("--rs", "--rip-source", dest="rip_source", type=str, help="Source of RIP (only for WEB-DL). Ex.: DSNP (Disney+), NFLX (Netflix), AMZN (Amazon), HBOM (HBO MAX)")
    args.add_argument("--vc", "--video-codec", dest="video_codec", type=str, required=False, help="Video codec, it will be detected from provided file. If error is raise when detection is not possible, please priovide it manually via this flag")
    args.add_argument("--ac", "--audio-codec", dest="audio_codec", type=str, required=False, help="Audio codec, it will be detected from provided file. If error is raise when detection is not possible, please priovide it manually via this flag")
    ns = args.parse_args()
    return Arguments(
        path=Path(ns.path),
        media_type=ns.media_type,
        name=ns.name,
        year=ns.year,
        episode=ns.episode,
        seasons=parse_series_num(ns.seasons),
        group=ns.group,
        rip_source=ns.rip_source,
        rip_type=ns.rip_type,
        video_codec=ns.video_codec,
        audio_codec=ns.audio_codec
    )

def parse_media(file: Path) -> MediaInfo:
    return MediaInfo.parse(file)

def extract_video_codec(track: Track) -> VideoCodecT | None:
    for value in track.to_data().values():
        if any(x in str(value) for x in ("x264", "H.264", "H264", "X264")):
            return "x264"
        elif any(x in str(value) for x in ("x265", "H.265", "H265", "X265")):
            return "x265"
    raise LookupError("Video codec not found, please provide it with -c option")

def get_video_info(mi: MediaInfo, *, user_video_codec: VideoCodecT | None) -> VideoInfo:
    video_track = mi.video_tracks[0]
    return VideoInfo(
        resolution=video_track.height,
        codec=user_video_codec or extract_video_codec(video_track)
    )

def format_audio_codec(audio_codec: str) -> AudioCodecT:
    if not isinstance(audio_codec, str):
        raise TypeError(f"Failed to detect audio codec for: {audio_codec}")
    if audio_codec.startswith("A_"):
        audio_codec = audio_codec[2:]
    return audio_codec.replace("-", "").replace(" ", ".").replace("_", ".")

def get_audio_info(mi: MediaInfo, *, user_audio_codec: AudioCodecT | None) -> list[str]:
    return list({format_audio_codec(x.to_data().get("codec_id")) for x in mi.audio_tracks}) if user_audio_codec is None else [user_audio_codec]

def get_lang_info(mi: MediaInfo) -> str:
    languages: set[str] = set()
    for track in [*mi.audio_tracks, *mi.text_tracks]:
        trackd: dict[str, str] = track.to_data()
        if (lang := trackd.get("language")):
            languages.add(lang)
        else:
            raise ValueError("No language provided")
    return list(languages)[0].upper() if len(languages) == 1 else "MULTi"
    
def main() -> None:
    args = parse_arguments()
    if args.rip_type == "WEB-DL":
        assert args.rip_source is not None, "If WEB-DL is specified You have to specify source."

    mediainfo = parse_media(args.path)

    lang = get_lang_info(mediainfo)
    video = get_video_info(mediainfo, user_video_codec=args.video_codec)
    audio = get_audio_info(mediainfo, user_audio_codec=args.audio_codec)

    result = args.name.replace(" ", ".")
    if args.year is not None:
        result += f".{args.year}"

    if args.media_type in ("season", "episode"):
        result += f".S{args.seasons[0] :02}"
        if args.media_type == "episode":
            result += f"E{args.episode :02}"
    if args.media_type == "series":
        result += f".S{min(args.seasons) :02}-S{max(args.seasons) :02}"

    result += f".{lang}.{video.resolution}p.{args.rip_source}.{args.rip_type}.{video.codec}.{audio[0]}-{args.group}"
    print(result)


if __name__ == "__main__":
    main()
