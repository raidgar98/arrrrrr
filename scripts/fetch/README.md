# Description and usage

## `vider.py`

### Description

Allows to fetch any video from vider, by automatic stream url extraction.

### Usage

```bash

python3 ./vider.py <link to website with video> <output path>
```

### Example:

```bash

python3 ./vider.py "https://vider.info/vid/+f8mmexx" "some_video.mp4"
```

### Known issues

If it returns 404 or something like "can't find a link" just open it in browser (on same IP, script is calling from) and resolve captcha, then re-run script


If you get "ban" for crawling, just clear cookies in web browser and hard refresh (ctrl + F5)
