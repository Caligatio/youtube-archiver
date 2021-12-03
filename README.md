# YouTube Archiver

YouTube Archiver is a clean HTML 5 web interface with a Python 3.7+ asyncio
multithreaded [youtube-dl] backend capable of downloading audio and/or video
from any source that youtube-dl supports. It targets a Docker-based deployment
but can be run without the use of Docker with some work.

![YouTube Archiver Screenshot](https://caligatio.github.io/youtube-archiver/screenshot.png)

## Usage

If you would like to use the pre-built image:

```console
# You may want to mount a volume into /data, it needs to be globally R/W
docker run -ti -p 8080:8080 ghcr.io/caligatio/youtube-archiver:master
```

If you would like to build the image yourself:

```console
git clone https://github.com/Caligatio/youtube-archiver.git
cd youtube-archiver
docker build . -t youtube-archiver

# You may want to mount a volume into /data, it needs to be globally R/W
docker run -ti -p 8080:8080 youtube-archiver
```

You should now be able to browse to http://localhost:8080 or equivalent
hostname/IP.

## Motivation

For those familiar with command line interfaces, youtube-dl is a great way of
downloading audio and/or video from a host of websites. This project seeks to
use a number of "best practice" settings to simplify youtube-dl's usage as well
as bundle dependencies such as FFmpeg. If you're already a happy user of
youtube-dl, you probably will not derive much benefit from this project.

YouTube Archiver does add some minor additional functionality on top of vanilla
youtube-dl:

- The merging of bestaudio+bestvideo and optional extraction of audio to a MP3
  file is performed in one invocation of youtube-dl.
- It will transcode all audio that will be embedded in video into MP4/AAC
  (increases compatibility with streaming devices).
- It will automatically grab and embed English subtitles for any video that
  provides subtitles.
- Users can queue up as many downloads as they wish at once without waiting for
  previous downloads to finish.

[youtube-dl]: https://ytdl-org.github.io/youtube-dl/
