# Description and usage

## `organise_by_filename.py`, `stop.py` and `rt_atomic_copy.sh`

### Description

These scripts copies finished data from `/downloads/temp` to `/downloads/complete/<Label>` and creates links for Jellyfin.

Benefit of this approach is that torrent directory structure is completly isolated from jellyfin metadata, images, subtitle "trash" files. 
Moreover metadata (with links) can be stored on SSD and thanks to that, whole service loads much faster and HDD used for torrent storage is not
loaded with accessing to metadata when users access it.

So this is how it looks in docker:

| Host path                         | Docker path |
|-----------------------------------|-------------------------- |
| /path/to/HDD/with/series          | /downloads/complete/Seriale |
| /path/to/HDD/with/series          | /downloads/complete/Anime |
| /path/to/HDD/with/movies          | /downloads/complete/Filmy |
| /path/to/HDD/with/movies          | /downloads/complete/Filmografia |
| /path/to/SSD/with/metadata        | /media |
| /path/to/dir/with/scripts         | /user-scripts |

### Configuration

Add this to .rtorrent.rc:

```
method.insert = d.atomic_copy_finalize, simple, \
  "execute.nothrow=sh,/user-scripts/rt_atomic_copy.sh,$d.data_path=,$d.get_finished_dir=,$d.custom1=,$d.hash=; \
   d.save_full_session="
```

### How it works?

First `stop.py` is called to pause torrent. Then rsync is started to securely copy whole data. After move `organise_by_filename.py` is called, 
which detects shows names and creates links to `/media` directory (series: `/media/series`, movies: `/media/movies`, etc...), replaces dir in rtorrent and starts it.


### Manual call

What if u created your own file, that you want to add to jellyfin, but without magic with rtorrent. Just call (inside container with rtorrent):

```bash
python3 /user-scripts/organise_by_filename.py "<Label>" noop /downloads/path/to/your/file
```

And this will also work and create proper links. 


### Limitations

Unfortunately this has its own limitations. First it depends on filename, which make it vulnerble if filename is not in `Series Name SxxExx.ext` format or movie filename does not contain year, but it works in about 90% of torrents. Rest of it i just sort writing mini scripts in bash.

