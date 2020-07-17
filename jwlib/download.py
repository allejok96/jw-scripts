from sys import stderr
import os
import shutil
import hashlib
import subprocess
import urllib.request
import urllib.parse
from typing import List, Optional

from . import msg
from .parse import Category, Media
from .arguments import Settings
from .output import format_filename


class MissingTimestampError(Exception):
    pass


def download_all(s: Settings, data: List[Category]):
    """Download/check media files"""

    wd = os.path.join(s.work_dir, s.sub_dir)  # work dir

    media_list = [x for cat in data
                  if cat.key not in s.exclude_categories or cat.home
                  for x in cat.contents
                  if isinstance(x, Media)]
    # Sort download queue with newest files first
    # This is important for the --free flag's disk_cleanup() to work as expected
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

    # Search for local media before initiating the download
    # (to get correct progress info for the download in next step)
    if s.quiet < 1:
        msg('scanning local files')
    for media in media_list:
        # Only run this check once per filename
        # (there may be multiple Media objects referring to the same file)
        name = _urlbasename(media.url)
        if name in checked_files:
            continue
        checked_files.append(name)

        # Skip previously deleted files
        if os.path.exists(os.path.join(wd, name + '.deleted')):
            if s.quiet < 1:
                msg('skipping previously deleted file: {}'.format(name))
            continue

        # Check existing files
        media.file = download_media(s, media, wd, check_only=True)
        if not media.file:
            download_list.append(media)

    # Download all files
    for media in download_list:
        if s.keep_free > 0:
            try:
                disk_cleanup(s, wd, media)
            except MissingTimestampError:
                if s.quiet < 2:
                    msg('low disk space and missing metadata, skipping: {}'.format(media.name))
                continue

        # Download the video
        if s.quiet < 2:
            print('[{}/{}]'.format(download_list.index(media) + 1, len(download_list)), end=' ', file=stderr)
        media.file = download_media(s, media, wd)


def download_subtitles(s: Settings, media: Media, directory: str):
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


def download_media(s: Settings, media: Media, directory: str, check_only=False):
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
                    msg('size mismatch, deleting: {}'.format(basename))
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


def disk_usage_info(s: Settings):
    """Display information about disk usage and maybe a warning"""

    # We create a directory here to prevent FileNotFoundError
    # if someone specified --free without --download they are dumb
    os.makedirs(s.work_dir, exist_ok=True)
    free = shutil.disk_usage(s.work_dir).free

    if s.quiet < 1:
        msg('note: old MP4 files in target directory will be deleted if space runs low')
        msg('free space: {:} MiB, minimum limit: {:} MiB'.format(free // 1024 ** 2, s.keep_free // 1024 ** 2))

    if s.warning and free < s.keep_free:
        message = '\nWarning:\n' \
                  'The disk usage currently exceeds the limit by {} MiB.\n' \
                  'If the limit was set too high by mistake, many or ALL \n' \
                  'currently downloaded videos may get deleted.\n'
        msg(message.format((s.keep_free - free) // 1024 ** 2))
        try:
            if not input('Do you want to proceed anyway? [y/N]: ') in ('y', 'Y'):
                exit(1)
        except EOFError:
            exit(1)


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
        # using urllib (for compatibility)
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


def disk_cleanup(s: Settings, directory: str, reference_media: Media):
    """Clean up old videos until there is enough space"""
    assert isinstance(s.keep_free, int)
    assert isinstance(reference_media.size, int)

    while True:
        space = shutil.disk_usage(directory).free
        needed = reference_media.size + s.keep_free
        if space > needed:
            break
        if s.quiet < 1:
            msg('free space: {:} MiB, needed: {:} MiB'.format(space // 1024 ** 2, needed // 1024 ** 2))

        # We dare not delete files if we don't know if they are older or newer than this one
        if not isinstance(reference_media.date, (int, float)):
            raise MissingTimestampError

        # Get the oldest .mp4 file in the working directory
        videos = []
        for file in os.listdir(directory):
            file = os.path.join(directory, file)
            if file.lower().endswith('.mp4') and os.path.isfile(file):
                videos.append((file, os.stat(file).st_mtime))
        if not videos:
            raise RuntimeError('disk limit reached, but no videos in {}'.format(directory))
        videos = sorted(videos, key=lambda x: x[1])
        oldest_file, oldest_date = videos[0]

        # If the reference date is older than the oldest file, exit the program.
        if reference_media.date <= oldest_date:
            if s.quiet < 1:
                msg('disk limit reached, all videos up to date')
            quit(0)

        # Delete the file and add a "deleted" marker
        if s.quiet < 2:
            msg('removing old video: {}'.format(oldest_file))
        os.remove(oldest_file)
        with open(oldest_file + '.deleted', 'w') as file:
            file.write('')
