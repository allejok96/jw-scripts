import argparse
import json
import signal
import subprocess
import time
from random import shuffle

from jwlib.common import Path, msg

class VideoManager:
    """Main class of jwb-offline

    Play video files, keep track of history
    """
    video = None  # type: Path
    start_time = None  # type: float
    pos = 0
    errors = 0

    def __init__(self, wd: Path, replay=0, cmd=None, verbose=False):
        """Initialize self.

        :param wd: working directory
        :keyword replay: seconds to replay of last video
        :keyword cmd: list with video player command
        """
        self.replay = replay
        self.wd = wd
        self.dump_file = wd / 'dump.json'
        self.history = []
        self.verbose = verbose

        if cmd and len(cmd) > 0:
            self.cmd = cmd
        else:
            self.cmd = ('omxplayer', '--pos', '{}', '--no-osd')

    def write_dump(self):
        """Dump data to JSON file"""
        d = {'video': self.video.str,
             'pos': self.calculate_pos(),
             'history': self.history}
        with self.dump_file.open('w') as output_file:
            output_file.write(json.dumps(d))

    def read_dump(self):
        """Load data from JSON file"""
        if self.dump_file.exists():
            with self.dump_file.open('r') as input_file:
                d = json.loads(input_file.read())
            if 'history' in d and type(d['history']) is list:
                self.history = d['history']
            if 'video' in d and type(d['video']) is str:
                self.video = Path(d['video'])
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
        msg('playing: ' + self.video.name)
        cmd = [arg.replace('{}', str(self.pos)) for arg in self.cmd] + [self.video.str]
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
        return [f for f in self.wd.iterdir() if f.is_mp4()]


def main():
    """jwb-offline

    Video player script
    """

    def handler(signal, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, handler)

    parser = argparse.ArgumentParser(prog='jwb-offline',
                                     usage='%(prog)s [DIR] [COMMAND]',
                                     description='Shuffle and play videos in DIR')
    parser.add_argument('dir',
                        nargs='?',
                        metavar='DIR',
                        default='.')
    parser.add_argument('cmd',
                        nargs='+',
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
    args.dir = Path(args.dir)

    m = VideoManager(args.dir, replay=args.replay, cmd=args.cmd, verbose=args.verbose)

    try:
        m.read_dump()
    except json.JSONDecodeError:
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
