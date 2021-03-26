import hashlib
import shutil
import subprocess
import urllib.parse
import urllib.request
from sys import stderr
from typing import List, Optional

from .common import Path, Settings, msg
from .parse import Category, Media


class MissingTimestampError(Exception):
    pass


class DiskLimitReached(Exception):
    pass


def download_all(s: Settings, data: List[Category]):
    """Download/check media files"""

    wd = s.work_dir / s.sub_dir

    media_list = [x for cat in data
                  for x in cat.contents
                  if isinstance(x, Media)]
    # Sort download queue with newest files first
    # This is important for the --free flag's disk_cleanup() to work as expected
    media_list = sorted(media_list, key=lambda x: x.date or 0, reverse=True)

    if s.download_subtitles:
        download_all_subtitles(s, media_list, wd)

    if not s.download:
        return

    # Search for local media before initiating the download
    # (to get correct progress info for the download in next step)
    if s.quiet < 1:
        msg('scanning local files')

    checked_files = []
    download_list = []
    for media in media_list:
        # Only run this check once per filename
        # (there may be multiple Media objects referring to the same file)
        if media.filename not in checked_files:
            checked_files.append(media.filename)
            if not check_media(s, media, wd):
                # Queue missing or bad files
                download_list.append(media)

    # Start downloading
    for num, media in enumerate(download_list):
        if s.keep_free > 0:
            try:
                disk_cleanup(s, wd, media)
            except MissingTimestampError:
                if s.quiet < 2:
                    msg('low disk space and missing metadata, skipping: {}'.format(media.name))
                continue
            except DiskLimitReached:
                return

        # Download the video
        if s.quiet < 2:
            print('[{}/{}]'.format(num + 1, len(download_list)), end=' ', file=stderr)
        download_media(s, media, wd)


def download_all_subtitles(s: Settings, media_list: List[Media], directory: Path):
    """Download VTT files from Media"""

    directory.mkdir(exist_ok=True)

    # Get all Media that needs subtitle downloaded
    queue = set(
        media for media in media_list
        if media.subtitle_url
        # Note: --fix-broken will re-download all subtitle files...
        if s.overwrite_bad or not (directory / media.subtitle_filename).exists()
    )

    for i, media in enumerate(queue):
        if s.quiet < 2:
            msg('[{}/{}] downloading: {}'.format(i + 1, len(queue), media.subtitle_filename))
        _curl(media.subtitle_url, file=directory / media.subtitle_filename, curl_path=None)


def check_media(s: Settings, media: Media, directory: Path):
    """Download media file and check it.

    Download file, check MD5 sum and size, delete file if it missmatches.

    :param s: Global settings
    :param media: a Media instance
    :param directory: dir where files are located
    :return: True if check is successful
    """
    file = directory / media.filename
    if not file.exists():
        return False

    # If we are going to fix bad files, check the existing ones
    if s.overwrite_bad:

        if media.size and file.size != media.size:
            if s.quiet < 2:
                msg('size mismatch: {}'.format(file))
            return False

        if s.checksums and media.md5 and _md5(file) != media.md5:
            if s.quiet < 2:
                msg('checksum mismatch: {}'.format(file))
            return False

    return True


def download_media(s: Settings, media: Media, directory: Path):
    """Download media file and check it.

    :param s: Global settings
    :param media: a Media instance
    :param directory: dir to save the files to
    :return: True if download was successful
    """
    directory.mkdir(exist_ok=True)
    file = directory / media.filename
    tmpfile = directory / (media.filename + '.part')

    if tmpfile:

        # If file is smaller, resume download
        if media.size and tmpfile.size < media.size:
            if s.quiet < 2:
                msg('resuming: {} ({})'.format(media.filename, media.name))
            _curl(media.url,
                  tmpfile,
                  resume=True,
                  rate_limit=s.rate_limit,
                  curl_path=s.curl_path,
                  progress=s.quiet < 1)

        # Check size
        if media.size and tmpfile.size != media.size:
            if s.quiet < 2:
                msg('size mismatch, deleting: {}'.format(tmpfile))
            # Always remove resumed files that have wrong size
            tmpfile.unlink()

        # Always check checksum on resumed files
        elif media.md5 and _md5(tmpfile) != media.md5:
            if s.quiet < 2:
                msg('checksum mismatch, deleting: {}'.format(tmpfile))
            # Always remove resumed files that are broken
            tmpfile.unlink()

        # Set timestamp to date of publishing, move and approve
        else:
            if media.date:
                tmpfile.set_mtime(media.date)
            tmpfile.rename(file)
            return True

    # Continuing to regular download
    if s.quiet < 2:
        msg('downloading: {} ({})'.format(media.filename, media.name))
    _curl(media.url,
          tmpfile,
          rate_limit=s.rate_limit,
          curl_path=s.curl_path,
          progress=s.quiet < 1)

    # Check exist and non-empty
    try:
        if tmpfile.size == 0:
            tmpfile.unlink()
            raise FileNotFoundError
    except FileNotFoundError:
        if s.quiet < 2:
            msg('download failed: {}'.format(media.filename))
        return False

    # Set timestamp to date of publishing, move and approve
    if media.date:
        tmpfile.set_mtime(media.date)
    tmpfile.rename(file)

    # Check size (log only)
    if media.size and file.size != media.size:
        if s.quiet < 2:
            msg('size mismatch: {}'.format(file))
        return False

    # Check MD5 if size was correct (optional, log only)
    if s.checksums and media.md5 and _md5(file) != media.md5:
        if s.quiet < 2:
            msg('checksum mismatch: {}'.format(file))

    return True


def disk_usage_info(s: Settings):
    """Display information about disk usage and maybe a warning"""

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


def _md5(file: Path):
    """Return MD5 of a file."""

    hash_md5 = hashlib.md5()
    with file.open('rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _curl(url: str, file: Path, resume=False, rate_limit='0', curl_path: Optional[str] = 'curl', progress=False):
    """Throttled file download by calling the curl command."""

    if curl_path:
        proc = [curl_path, url, '-o', file.str]

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
            request.add_header('Range', 'bytes={}-'.format(file.size))
            # Append data to file, instead of overwriting
            file_mode = 'ab'

        response = urllib.request.urlopen(request)

        # Write out 1MB at a time, so whole file is not lost if interrupted
        with file.open(file_mode) as f:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)


def disk_cleanup(s: Settings, directory: Path, reference_media: Media):
    """Clean up old videos until there is enough space"""
    assert s.keep_free
    assert reference_media.size

    # As this runs before download, the subdirectory may not exist
    if not directory.exists():
        return

    while True:
        space = shutil.disk_usage(directory.str).free
        needed = reference_media.size + s.keep_free
        if space > needed:
            break
        if s.quiet < 1:
            msg('free space: {:} MiB, needed: {:} MiB'.format(space // 1024 ** 2, needed // 1024 ** 2))

        # We dare not delete files if we don't know if they are older or newer than this one
        if not reference_media.date:
            raise MissingTimestampError

        try:
            # Get the oldest .mp4 file in the working directory
            oldest = min((f for f in directory.iterdir() if f.is_mp4()), key=lambda f: f.mtime)
        except ValueError:
            msg('cannot free more disk space, no videos in {}'.format(directory))
            exit(1)
            raise

        # If the reference date is older than the oldest file, exit the program.
        if reference_media.date <= oldest.mtime:
            if s.quiet < 1:
                msg('disk limit reached, all videos up to date')
            raise DiskLimitReached

        # Delete the file and add a "deleted" marker
        if s.quiet < 2:
            msg('removing old video: {}'.format(oldest))
        oldest.unlink()


def copy_files(s: Settings):
    """jwb-index --import

    Fancy copy of files from one directory to another
    """

    dest_dir = s.work_dir / s.sub_dir
    dest_dir.mkdir(exist_ok=True)

    # Create a list of all mp4 files to be copied
    source_files = []
    for source in s.import_dir.iterdir():
        try:
            # Just a simple size check, no checksum etc
            if source.is_mp4() and source.size != (dest_dir / source.name).size:
                source_files.append(source)
        except OSError:
            pass

    # Newest file first
    source_files.sort(key=lambda x: x.date, reverse=True)

    total = len(source_files)
    for source_file in source_files:
        if s.keep_free > 0:
            disk_cleanup(s, directory=dest_dir, reference_media=source_file)

        if s.quiet < 1:
            i = source_files.index(source_file)
            msg('copying [{}/{}]: {}'.format(i + 1, total, source_file.name))

        shutil.copy2(source_file.path, dest_dir / source_file.name)

