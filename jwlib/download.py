from sys import stderr
import os
import shutil
import hashlib
import subprocess
import urllib.request
import urllib.parse
from typing import List, Optional

from .parse import msg, Category, Media
from .arguments import JwbSettings
from .output import format_filename


def download_all(s: JwbSettings, data: List[Category]):
    """Download/check media files"""

    wd = os.path.join(s.work_dir, s.sub_dir)  # work dir

    media_list = [x for cat in data
                  if cat.key not in s.exclude_categories or cat.home
                  for x in cat.contents
                  if isinstance(x, Media)]
    media_list = sorted(media_list, key=lambda x: x.date or 0, reverse=True)

    if s.download_subtitles:
        subtitle_list = [m for m in media_list if m.subtitle_url]
        for media in subtitle_list:
            if s.quiet < 2:
                print('[{}/{}]'.format(subtitle_list.index(media) + 1, len(subtitle_list)), end=' ', file=stderr)
            download_subtitles(s, media, wd)

    if not s.download:
        return

    # Trim down the list of files that need to be downloaded
    download_list = []
    checked_files = []

    for media in media_list:
        # Only run this check once per filename
        name = _urlbasename(media.url)
        if name in checked_files:
            continue
        checked_files.append(name)

        # Skip previously deleted files
        if os.path.exists(os.path.join(wd, name + '.deleted')):
            continue

        # Search for local media and delete broken files before initiating the download
        media.file = download_media(s, media, wd, check_only=True)
        if not media.file:
            download_list.append(media)

    # Download all files
    for media in download_list:
        # Clean up until there is enough space
        while s.keep_free > 0:
            space = shutil.disk_usage(wd).free
            needed = media.size + s.keep_free
            if space > needed:
                break
            if s.quiet < 1:
                msg('free space: {:} MiB, needed: {:} MiB'.format(space // 1024 ** 2, needed // 1024 ** 2))
            delete_oldest(wd, media.date, s.quiet)

        # Download the video
        if s.quiet < 2:
            print('[{}/{}]'.format(download_list.index(media) + 1, len(download_list)), end=' ', file=stderr)
        media.file = download_media(s, media, wd)


def download_subtitles(s: JwbSettings, media: Media, directory: str):
    """Download VTT files from Media

    :param s: Global settings
    :param media: a Media instance
    :param directory: dir to save the files to
    """
    os.makedirs(directory, exist_ok=True)

    basename = _urlbasename(media.subtitle_url)
    if s.friendly_subtitle_filenames:
        suffix = os.path.splitext(basename)[1]
        basename = format_filename(media.name + suffix, safe=s.safe_filenames)
    if s.quiet < 2:
        msg('downloading: {}'.format(basename, media.name))
    _curl(media.subtitle_url, file=os.path.join(directory, basename), curl_path=None)


def download_media(s: JwbSettings, media: Media, directory: str, check_only=False):
    """Download media file and check it.

    Download file, check MD5 sum and size, delete file if it missmatches.

    :param s: Global settings
    :param media: a Media instance
    :param directory: dir to save the files to
    :param check_only: bool, True means no downloading
    :return: filename, or None if unsuccessful
    """
    if not os.path.exists(directory) and not s.download:
        return None
    os.makedirs(directory, exist_ok=True)

    basename = _urlbasename(media.url)
    file = os.path.join(directory, basename)

    # Only try resuming and downloading once
    resumed = False
    downloaded = False

    while True:

        if os.path.exists(file):

            # Set timestamp to date of publishing
            # NOTE: Do this before checking _checked_files since
            # this is not done for newly renamed .part files!
            if media.date:
                os.utime(file, (media.date, media.date))

            if os.path.getsize(file) == media.size or not media.size:
                # File size is OK or unknown - Validate checksum
                if s.checksums and media.md5 and _md5(file) != media.md5:
                    # Checksum is bad - Remove
                    if s.quiet < 2:
                        msg('checksum mismatch, deleting: {}'.format(basename))
                    os.remove(file)
                else:
                    # Checksum is correct or unknown
                    return file
            else:
                # File size is bad - Delete
                if s.quiet < 2:
                    msg('size mismatch, deleting: {}'.format(basename + '.part'))
                os.remove(file)

        elif check_only:
            # The rest of this method is only applicable in download mode
            return None

        elif os.path.exists(file + '.part'):

            fsize = os.path.getsize(file + '.part')

            if fsize == media.size or not media.size:
                # File size is OK - Validate checksum
                if s.checksums and media.md5 and _md5(file + '.part') != media.md5:
                    # Checksum is bad - Remove
                    if s.quiet < 2:
                        msg('checksum mismatch, deleting: {}'.format(basename + '.part'))
                    os.remove(file + '.part')
                else:
                    # Checksum is correct or unknown - Move and approve
                    os.rename(file + '.part', file)
                    return file
            elif fsize < media.size and not resumed:
                # File is smaller - Resume download once
                resumed = True
                if s.quiet < 2:
                    msg('resuming: {} ({})'.format(basename + '.part', media.name))
                _curl(media.url,
                      file + '.part',
                      resume=True,
                      rate_limit=s.rate_limit,
                      curl_path=s.curl_path,
                      progress=s.quiet < 1)
            else:
                # File size is bad - Remove
                if s.quiet < 2:
                    msg('size mismatch, deleting: {}'.format(basename + '.part'))
                os.remove(file + '.part')

        else:
            # Download whole file once
            if not downloaded:
                downloaded = True
                if s.quiet < 2:
                    msg('downloading: {} ({})'.format(basename, media.name))
                _curl(media.url,
                      file + '.part',
                      rate_limit=s.rate_limit,
                      curl_path=s.curl_path,
                      progress=s.quiet < 1)
            else:
                # If we get here, all tests have failed.
                # Resume and regular download too.
                # There is nothing left to do.
                if s.quiet < 2:
                    msg('failed to download: {} ({})'.format(basename, media.name))
                return None


def _urlbasename(string: str):
    return os.path.basename(urllib.parse.urlparse(string).path)


def _md5(file: str):
    """Return MD5 of a file."""
    hash_md5 = hashlib.md5()
    with open(file, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _curl(url: str, file: str, resume=False, rate_limit='0', curl_path: Optional[str] = 'curl', progress=False):
    """Throttled file download by calling the curl command."""
    if curl_path:
        proc = [curl_path, url, '-o', file]

        if rate_limit != '0':
            proc.append('--limit-rate')
            proc.append(rate_limit)
        if progress:
            proc.append('--progress-bar')
        else:
            proc.append('--silent')
        if resume:
            # Download what is missing at the end of the file
            proc.append('--continue-at')
            proc.append('-')

        subprocess.call(proc, stderr=stderr)

    else:
        # If there is no rate limit, use urllib (for compatibility)
        request = urllib.request.Request(url)
        file_mode = 'wb'

        if resume:
            # Ask server to skip the first N bytes
            request.add_header('Range', 'bytes={}-'.format(os.stat(file).st_size))
            # Append data to file, instead of overwriting
            file_mode = 'ab'

        response = urllib.request.urlopen(request)

        # Write out 1MB at a time, so whole file is not lost if interrupted
        with open(file, file_mode) as f:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)


def delete_oldest(wd: str, max_date: int, quiet=0):
    """Delete the oldest .mp4 file in the work_dir

    If oldest video is newer than max_date, exit the program.

    :param wd: directory to look for videos
    :param max_date: seconds since epoch
    :param quiet: info level, 0 = all, 1 = only deleted, 2 = nothing
    """
    videos = []
    for file in os.listdir(wd):
        file = os.path.join(wd, file)
        if file.lower().endswith('.mp4') and os.path.isfile(file):
            videos.append((file, os.stat(file).st_mtime))
    if len(videos) == 0:
        raise (RuntimeError('cannot free any disk space, no videos found'))
    videos = sorted(videos, key=lambda x: x[1])
    oldest_file, oldest_date = videos[0]

    if max_date and max_date <= oldest_date:
        if quiet < 1:
            msg('disk limit reached, all videos up to date')
        quit(0)

    if quiet < 2:
        msg('removing {}'.format(oldest_file))
    os.remove(oldest_file)
    # Add a "deleted" marker
    with open(oldest_file + '.deleted', 'w') as file:
        file.write('')
