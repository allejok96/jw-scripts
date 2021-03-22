import argparse
import json
import os
import shutil
import signal
import subprocess
import time
from random import shuffle

from jwlib.common import Settings, msg
from jwlib.download import disk_cleanup


class File:
    def __init__(self, directory: str, filename: str):
        self.name = filename
        self.path = os.path.join(directory, filename)
        try:
            stat = os.stat(self.path)
            self.size = stat.st_size
            self.date = stat.st_mtime
        except FileNotFoundError:
            self.size = None
            self.date = None

    def isfile(self):
        return os.path.isfile(self.path)

    def ismp4(self):
        return self.path.lower().endswith('.mp4')


def copy_files(s: Settings):
    dest_dir = os.path.join(s.work_dir, s.sub_dir)

    # Create a list of all mp4 files to be copied
    source_files = []
    for name in os.listdir(s.import_dir):
        source_file = File(s.import_dir, name)
        if not source_file.isfile() or not source_file.ismp4():
            continue
        dest_file = File(dest_dir, name)
        # Just a simple size check, no checksum etc
        if source_file.size != dest_file.size:
            source_files.append(source_file)

    # Newest file first
    source_files.sort(key=lambda x: x.date, reverse=True)

    os.makedirs(dest_dir, exist_ok=True)

    total = len(source_files)
    for source_file in source_files:
        if s.keep_free > 0:
            disk_cleanup(s, directory=dest_dir, reference_media=source_file)

        if s.quiet < 1:
            i = source_files.index(source_file)
            msg('copying [{}/{}]: {}'.format(i + 1, total, source_file.name))

        shutil.copy2(source_file.path, os.path.join(dest_dir, source_file.name))


class VideoManager:
    """Play video files, keep track of history"""
    # Can be changed by user

    # Will be set by VideoManager
    video = None
    start_time = None
    pos = 0
    errors = 0

    def __init__(self, wd, replay=0, cmd=None, verbose=False):
        """Initialize self.

        :param wd: working directory
        :keyword replay: seconds to replay of last video
        :keyword cmd: list with video player command
        """
        self.replay = replay
        self.wd = wd
        self.dump_file = os.path.join(wd, 'dump.json')
        self.history = []
        self.verbose = verbose

        if cmd and len(cmd) > 0:
            self.cmd = cmd
        else:
            self.cmd = ('omxplayer', '--pos', '{}', '--no-osd')

    def write_dump(self):
        """Dump data to JSON file"""
        d = {'video': self.video,
             'pos': self.calculate_pos(),
             'history': self.history}
        with open(self.dump_file, 'w') as output_file:
            output_file.write(json.dumps(d))

    def read_dump(self):
        """Load data from JSON file"""
        if os.path.exists(self.dump_file):
            with open(self.dump_file, 'r') as input_file:
                d = json.loads(input_file.read())
            if 'history' in d and type(d['history']) is list:
                self.history = d['history']
            if 'video' in d and type(d['video']) is str:
                self.video = d['video']
            if 'pos' in d and type(d['pos']) is int:
                self.pos = d['pos']

    def set_random_video(self):
        """Get a random video from working directory"""
        if self.video:
            self.start_time = time.time()
            return True
        files = self.list_videos()
        shuffle(files)
        for vid in files:
            if vid in self.history:
                continue
            self.video = vid
            self.pos = 0
            return True
        return False

    def calculate_pos(self):
        """Calculate the playback position in the currently playing video"""
        if self.start_time:
            p = int(time.time() - self.start_time + self.pos - self.replay)
            if p < 0:
                p = 0
            return p
        else:
            return 0

    def play_video(self):
        """Play a video"""
        self.write_dump()
        msg('playing: ' + self.video)
        cmd = [arg.replace('{}', str(self.pos)) for arg in self.cmd] + [os.path.join(self.wd, self.video)]
        self.start_time = time.time()
        if self.verbose:
            subprocess.call(cmd)
        else:
            subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if self.calculate_pos() == 0:
            self.errors = self.errors + 1
        else:
            self.errors = 0
        if self.errors > 10:
            raise RuntimeError('video player restarting too quickly')

        self.add_to_history(self.video)
        self.video = None

    def add_to_history(self, video):
        """Add a video to the history and trim it to half of the amount of videos"""
        max_len = len(self.list_videos()) // 2
        self.history.append(video)
        self.history = self.history[-max_len:]

    def list_videos(self):
        """Return a list of all MP4 files in working dir"""
        v = [f for f in os.listdir(self.wd) if f.lower().endswith('.mp4') if os.path.isfile(os.path.join(self.wd, f))]
        return v


def handler(signal, frame):
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGTERM, handler)

    parser = argparse.ArgumentParser(prog='jwb-offline',
                                     usage='%(prog)s [DIR] [COMMAND]',
                                     description='Shuffle and play videos in DIR')
    parser.add_argument('dir',
                        nargs='?',
                        metavar='DIR',
                        default='.')
    parser.add_argument('cmd',
                        nargs=argparse.REMAINDER,
                        metavar='COMMAND',
                        help='video player command, "{}" gets replaced by starting position in secs')
    parser.add_argument('--replay-sec',
                        metavar='SEC',
                        type=int,
                        default=30,
                        dest='replay',
                        help='seconds to replay after a restart')
    parser.add_argument('--verbose',
                        action='store_true',
                        help='show video player output')

    args = parser.parse_args()

    m = VideoManager(args.dir, replay=args.replay, cmd=args.cmd, verbose=args.verbose)

    # JSONDecodeError was added to Python 3.5
    if hasattr(json, 'JSONDecodeError'):
        JSONDecodeError = json.JSONDecodeError
    else:
        JSONDecodeError = ValueError

    try:
        m.read_dump()
    except JSONDecodeError:
        pass

    showmsg = True
    try:
        while True:
            if m.set_random_video():
                m.play_video()
                showmsg = True
            else:
                if showmsg:
                    msg('no videos to play yet')
                    showmsg = False
                time.sleep(10)
                continue
    except KeyboardInterrupt:
        msg('aborted')
        m.write_dump()


if __name__ == '__main__':
    main()
