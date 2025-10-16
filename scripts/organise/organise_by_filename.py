from __future__ import annotations
import contextlib
import sys
import re
from pathlib import Path
from dataclasses import dataclass
import xmlrpc.client


SUPPORTED_CATEGORIES = [
    "Filmy",
    "Seriale",
    "Anime",
    "Filmografia"
]
IGNORED_PATHS = (f"/downloads/complete/{x}" for x in SUPPORTED_CATEGORIES)
VIDEO_EXTENSIONS: tuple = ('.mkv', '.mp4', '.m4v', '.avi', '.mov', '.ts')
LINK_FILE_DIR = Path("/media/")
MOVIES_FILE_DIR = LINK_FILE_DIR / "movies"
SERIES_FILE_DIR = LINK_FILE_DIR / "series"
HOST_PATH = Path("/downloads")

@dataclass
class MovieInfo:
    name: str
    year: str
    host_path: Path
    path: Path
    extension: str

    def __post_init__(self) -> None:
        self.name = remove_psig_prefix(self.name)

    @property
    def basename(self) -> str:
        return f"{self.name} ({self.year})"

    @property
    def filename(self) -> str:
        return f"{self.basename}{self.extension}"

    @property
    def media_folder(self) -> Path:
        return MOVIES_FILE_DIR / self.basename

    @property
    def media_link(self) -> Path:
        return self.media_folder / self.filename

@dataclass
class EpisodeInfo:
    episode_num: int
    season_num: int
    series_name: str
    host_path: Path
    extension: str

    def __post_init__(self) -> None:
        if ("Pokemon" in self.series_name) or ("Pokémon" in self.series_name):
            self.series_name = "Pokemon"
        self.series_name = remove_psig_prefix(self.series_name)

    @property
    def media_series_dir(self) -> Path:
        return SERIES_FILE_DIR / self.series_name

    @property
    def media_season_dir(self) -> Path:
        return self.media_series_dir / f"Season {self.season_num}"

    @property
    def media_episode_file(self) -> Path:
        return self.media_season_dir / f"{self.series_name} S{self.season_num:02d}E{self.episode_num}{self.extension}"

def remove_psig_prefix(name: str) -> str:
    prefix = "psig-"
    if name.startswith(prefix):
        return name[len(prefix):]
    return name

def update_directory_and_save(infohash: str, basedir: str):
    """
    Ustaw katalog torrenta i zapisz całą sesję w jednym multicall.
    Zwraca listę odpowiedzi metod XML-RPC.

    :param infohash: 40-znakowy hash (hex)
    :param basedir:  docelowy katalog (istniejący lub do utworzenia przez rTorrent/Twoje procesy)
    """
    if infohash == "noop":
        return None
    ih = infohash.strip().lower()
    if not (len(ih) == 40 and all(c in "0123456789abcdef" for c in ih)):
        raise ValueError("infohash musi być 40-znakowym ciągiem hex.")

    server = xmlrpc.client.ServerProxy("http://127.0.0.1:8000/RPC2", allow_none=True)
    calls = [
        {"methodName": "d.open",       "params": [ih]},
        {"methodName": "d.check_hash", "params": [ih]},
        {"methodName": "d.directory.set", "params": [ih, basedir]},
        # {"methodName": "session.save",    "params": []},
        {"methodName": "d.open",       "params": [ih]},
        # {"methodName": "d.check_hash", "params": [ih]},
        {"methodName": "d.start", "params": [ih]},
        {"methodName": "session.save",    "params": []},
    ]
    print("sending:", calls)
    return server.system.multicall(calls)


def parse_movie(file_path: Path) -> MovieInfo:
    if not file_path.is_file():
        for path in file_path.rglob('*'):
            if path.suffix in VIDEO_EXTENSIONS:
                file_path = path
                break

    assert file_path.is_file(), "No valid video file found."
    year_pattern: re.Pattern = re.compile(r'([\(\.]?((?:19|20)\d{2})(?!p)[\)\.]?)')
    if (result := (year_pattern.search(file_path.name) or year_pattern.search(file_path.parent.name))) is None:
        raise ValueError(f"Year not found in filename: `{file_path.name}`")

    year: str = result.group(2)
    name: str = file_path.name[:result.start(1)].replace('.', ' ').strip(" ([")
    extension: str = file_path.suffix
    host_path = HOST_PATH.joinpath(*file_path.parts[2:])

    return MovieInfo(
        name=name,
        year=year,
        host_path=host_path,
        path=file_path,
        extension=extension
    )

def parse_filmography(file_path: Path) -> list[MovieInfo]:
    result: list[MovieInfo] = []
    for path in file_path.rglob('*'):
        if path.suffix in VIDEO_EXTENSIONS:
            result.append(parse_movie(path))
    return result

def process_episode(file: Path) -> EpisodeInfo | None:
    assert file.is_file(), f"path {file.as_posix()} should be file!"
    episode_pattern: re.Pattern = re.compile(r'([sS](\d{1,2})\s*[eE](\d{1,3}[abcdefgh]?))')
    backup_episode_pattern: re.Pattern = re.compile(
        r'(?:[sS](?:(?:[eE][aA][sS][oO][nN])|(?:[eE][zZ][oO][nN]))?\s?(\d{1,2})(?!-)).*'
        r'(?:[eE](?:(?:[pP][iI][zZ][oO][dD])|(?:[pP][iI][sS][oO][dD][eE]))?\s?(\d{1,3}[abcdefgh]?)(?!-)).*'
    )
    year_pattern: re.Pattern = re.compile(r'([\(\.]?((?:19|20)\d{2})(?!p)[\)\.]?)')
    episodes: list[EpisodeInfo] = []

    if file.suffix not in VIDEO_EXTENSIONS:
        return None
    if (result := episode_pattern.search(file.name)) is None:
        full_path = file.as_posix()
        if (result_back := backup_episode_pattern.search(full_path)) is None:
            print(f"Skipping file (no episode info found): {file}")
            return None
        season_num = int(result_back.group(1))
        episode_num = result_back.group(2)
        series_name = (" ".join(full_path[0:min(result_back.start(1), len(full_path))].split('/')[-1].split('.')[:-1])).strip()
    else:
        year_pos = len(file.name)
        year_match = year_pattern.search(file.name)
        if year_match:
            year_pos = year_match.start(1)
        season_num: int = int(result.group(2))
        episode_num: int = result.group(3)
        series_name: str = file.name[:min(result.start(1), year_pos)].replace('.', ' ').strip()

    extension: str = file.suffix
    host_path = HOST_PATH.joinpath(*file.parts[2:])

    return EpisodeInfo(
        episode_num=episode_num,
        season_num=season_num,
        series_name=series_name,
        host_path=host_path,
        extension=extension
    )

def parse_series_dir(path: Path) -> list[EpisodeInfo]:
    episode_pattern: re.Pattern = re.compile(r'([sS](\d{1,2})\s*[eE](\d{1,3}[abcdefgh]?))')
    backup_episode_pattern: re.Pattern = re.compile(
        r'(?:[sS](?:(?:[eE][aA][sS][oO][nN])|(?:[eE][zZ][oO][nN]))?\s?(\d{1,2})(?!-)).*'
        r'(?:[eE](?:(?:[pP][iI][zZ][oO][dD])|(?:[pP][iI][sS][oO][dD][eE]))?\s?(\d{1,3}[abcdefgh]?)(?!-)).*'
    )
    year_pattern: re.Pattern = re.compile(r'([\(\.]?((?:19|20)\d{2})(?!p)[\)\.]?)')
    episodes: list[EpisodeInfo] = []

    if path.is_file():
        if (res := process_episode(path)) is not None:
            return [res]
        return []

    for file in path.rglob('*'):
        result = process_episode(file)
        if result is None:
            continue
        episodes.append(result)

    return episodes

def main():
    category = sys.argv[1]
    info_hash = sys.argv[2]
    file_path = Path(" ".join(sys.argv[3:]))
    basepath = file_path.parent

    print(f"Category: {category}, Path: {file_path}, Basepath: {basepath}")
    is_update_required = info_hash != "noop"

    if category not in SUPPORTED_CATEGORIES:
        print(f"Category '{category}' is not supported.")
        print("Updating torrent basedir", info_hash, update_directory_and_save(info_hash, basepath.as_posix()))
        return

    elif category == "Filmy":
        info = parse_movie(file_path)
        print(f"Linking movie: {info.media_link} -> {info.host_path}")
        info.media_folder.mkdir(exist_ok=True, parents=True)
        with contextlib.suppress(FileExistsError):
            info.media_link.symlink_to(info.host_path)
        if is_update_required:
            print("Updating torrent basedir", info_hash, update_directory_and_save(info_hash, basepath.as_posix()))

    elif category == "Filmografia":
        for movie in parse_filmography(file_path):
            print(f"Linking movie: {movie.media_link} -> {movie.host_path}")
            movie.media_folder.mkdir(exist_ok=True, parents=True)
            with contextlib.suppress(FileExistsError):
                movie.media_link.symlink_to(movie.host_path)
        if is_update_required:
            print("Updating torrent basedir", info_hash, update_directory_and_save(info_hash, basepath.as_posix()))

    elif category in ["Seriale", "Anime"]:
        episodes = parse_series_dir(file_path)
        assert len(episodes) > 0, "No valid episodes found."
        episodes[0].media_series_dir.mkdir(exist_ok=True, parents=True)
        for episode in episodes:
            episode.media_season_dir.mkdir(exist_ok=True, parents=True)
            print(f"Linking series: {episode.media_episode_file} -> {episode.host_path}")
            with contextlib.suppress(FileExistsError):
                episode.media_episode_file.symlink_to(episode.host_path)
        if is_update_required:
            print("Updating torrent basedir", info_hash, update_directory_and_save(info_hash, basepath.as_posix()))


if __name__ == "__main__":
    main()
