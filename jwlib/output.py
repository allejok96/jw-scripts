import os

pj = os.path.join


def _truncate_file(file, string=''):
    """Create a file and the parent directories.

    Arguments:
    file - File to create/overwrite

    Keyword arguments:
    string - A string to write to the file
    """
    d = os.path.dirname(file)
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

    # Don't truncate non-empty files
    if os.path.exists(file) and os.stat(file).st_size != 0:
        return

    with open(file, 'w') as f:
        f.write(string)


class Output:
    """Base output class.

    This class does nothing.
    """
    
    def __init__(self, work_dir=None):
        """Set working dir and dir for media download.
        
        Keyword arguments:
            work_dir -- Working directory
        """
        if not work_dir:
            work_dir = os.getcwd()
        self.work_dir = work_dir
        self.media_dir = work_dir

    def _nothing(self, *args, **keywords):
        pass

    set_cat, save_subcat, save_media = _nothing, _nothing, _nothing


class OutputStdout(Output):
    """Output text only."""

    def save_media(self, media):
        """Output URL/filename from Media instance to stdout."""
        if media.file:
            print(os.path.relpath(media.file, self.media_dir))
        else:
            print(media.url)


class OutputM3U(Output):
    """Create a M3U playlist tree."""

    def __init__(self, work_dir, subdir):
        super().__init__(work_dir)
        self._subdir = subdir
        self._output_file = None
        self._inserted_subdir = ''
        self.file_ending = '.m3u'
        self.media_dir = pj(self.work_dir, self._subdir)

    def save_media(self, media):
        """Write media entry to playlist."""
        if media.file:
            source = pj('.', self._subdir, os.path.basename(media.file))
        else:
            source = media.url

        self.write_to_file(source, media.name)

    def save_subcat(self, cat, name):
        """Write link to another category, i.e. playlist, to the current one."""
        name = name.upper()
        source = pj('.', self._inserted_subdir, cat + self.file_ending)
        self.write_to_file(source, name)

    def set_cat(self, cat, name):
        """Set destination playlist file."""
        if not self._output_file:
            # The first time THIS method runs:
            # The current (first) file gets saved outside the subdir,
            # all other data (later files) gets saved inside the subdir,
            # so all paths in the current file must have the subdir prepended.
            self._inserted_subdir = self._subdir
            self._output_file = pj(self.work_dir, name + self.file_ending)
        else:
            # The second time and forth:
            # Don't prepend the subdir no more
            # Save data directly in the subdir
            self._inserted_subdir = ''
            self._output_file = pj(self.work_dir, self._subdir, cat + self.file_ending)

        # Since we want to start on a clean file, remove the old one
        if os.path.exists(self._output_file):
            os.remove(self._output_file)

    def write_to_m3u(self, source, name, file=None):
        """Write entry to a M3U playlist file."""
        if not file:
            file = self._output_file
        _truncate_file(file, string='#EXTM3U\n')
        with open(file, 'a') as f:
            f.write('#EXTINF:0,' + name + '\n' + source + '\n')

    write_to_file = write_to_m3u


class OutputM3UCompat(OutputM3U):
    """Create multiple M3U playlists."""

    def set_cat(self, cat, name):
        """Set/remove destination playlist file."""
        self._output_file = pj(self.work_dir, cat + ' - ' + name + self.file_ending)
        # Since we want to start on a clean file, remove the old one
        if os.path.exists(self._output_file):
            os.remove(self._output_file)

    def save_subcat(self, cat, name):
        """Do nothing.

        Unlike the parent class, this class doesn't save links to other categories,
        e.g. other playlists, inside the current playlist.
        """
        pass


class OutputHTML(OutputM3U):
    """Create a HTML file."""

    def __init__(self, work_dir, subdir):
        super().__init__(work_dir, subdir)
        self.file_ending = '.html'

    def write_to_html(self, source, name, file=None):
        """Write a HTML file with a hyperlink to a media file."""
        if not file:
            file = self._output_file

        _truncate_file(file, string='<!DOCTYPE html>\n<head><meta charset="utf-8" /></head>')

        with open(file, 'a') as f:
            f.write('\n<a href="{0}">{1}</a><br>'.format(source, name))

    write_to_file = write_to_html


class OutputFilesystem(Output):
    """Creates a directory structure with symlinks to videos"""

    def __init__(self, work_dir, subdir):
        super().__init__(work_dir)
        self._subdir = subdir
        self.media_dir = pj(work_dir, subdir)
        self._output_dir = None

    def set_cat(self, cat, name):
        """Create a directory (category) where symlinks will be saved"""
        output_dir_before = self._output_dir
        
        self._output_dir = pj(self.work_dir, self._subdir, cat)
        if not os.path.exists(self._output_dir):
            os.makedirs(self._output_dir)

        # First time: create link outside subdir
        if output_dir_before is None:
            link = pj(self.work_dir, name)
            if not os.path.lexists(link):
                dir_fd = os.open(self._output_dir, os.O_RDONLY)
                # Note: the source will be relative
                source = pj(self._subdir, cat)
                os.symlink(source, link, dir_fd=dir_fd)

    def save_subcat(self, cat, name):
        """Create a symlink to a directory (category)"""
        dir_ = pj(self.work_dir, self._subdir, cat)
        if not os.path.exists(dir_):
            os.makedirs(dir_)

        source = pj('..', cat)
        link = pj(self._output_dir, name)

        if not os.path.lexists(link):
            dir_fd = os.open(self._output_dir, os.O_RDONLY)
            os.symlink(source, link, dir_fd=dir_fd)

    def save_media(self, media):
        """Create a symlink to a media file"""
        if not media.file:
            return

        source = pj('..', os.path.basename(media.file))
        ext = os.path.splitext(media.file)[1]
        link = pj(self._output_dir, media.name + ext)

        if not os.path.lexists(link):
            dir_fd = os.open(self._output_dir, os.O_RDONLY)
            os.symlink(source, link, dir_fd=dir_fd)

    def clean_symlinks(self, clean_all=False):
        """Clean out broken symlinks from work_dir/subdir/*/"""
        d = pj(self.work_dir, self._subdir)

        if not os.path.exists(d):
            return

        for sd in os.listdir(d):
            sd = pj(d, sd)
            if os.path.isdir(sd):
                for L in os.listdir(sd):
                    L = pj(sd, L)
                    if clean_all or os.path.lexists(L):
                        os.remove(L)

                        
class OutputQueue(Output):
    """Queues media objects"""

    def __init__(self, work_dir):
        super().__init__(work_dir)
        self.queue = []

    def save_media(self, media):
        """Add a media object to the queue"""
        self.queue.append(media)


class OutputStreaming(Output):
    """Queue URLs from a single category"""
    
    def __init__(self):
        super().__init__()
        self.queue = []
        self.pos = 0

    def save_media(self, media):
        """Add an URL to the queue"""
        self.queue.append(media.url)

    def set_cat(self, cat, name):
        """Reset queue"""
        self.queue = []
