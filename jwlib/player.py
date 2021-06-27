import argparse
import json
import random
import subprocess
import time

from jwlib.common import Path, msg


class NoVideos(Exception):
    pass


class RuntimeInfo:
    def __init__(self):
        # List of names of played videos with the most recent as the last
        self.history = []
        # Where the last video was paused (in seconds)
        self.resume = 0
        # When the last video started playing (as a POSIX timestamp)
        self.playback_started = 0.0
        # Number of times the video player exited too quickly
        self.failed_playbacks = 0

    @classmethod
    def load(cls, path: Path):
        try:
            with path.open() as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}

        info = cls()
        info.history = data.get('history', [])
        info.resume = int(data.get('resume', 0))
        return info

    def save(self, path: Path):
        data = {
            'history': self.history,
            'resume': int(time.time() - self.playback_started) if self.playback_started else 0
        }
        with path.open('w') as f:
            json.dump(data, f)

    def register_start(self, video_name: str):
        try:
            self.history.remove(video_name)
        except ValueError:
            pass
        self.history.append(video_name)
        self.playback_started = time.time()
        self.resume = 0

    def register_stop(self):
        if self.failed_playbacks > 10:
            raise RuntimeError('video player restarting too quickly')
        elif time.time() - self.playback_started < 0:
            self.failed_playbacks += 1
        else:
            self.failed_playbacks = 0

        self.playback_started = 0.0

    def get_resume(self, dir: Path, rewind: int = 0):
        if self.resume and self.history:
            video = dir / self.history[-1]
            if video.is_mp4():
                # Rewind, but not past 0
                return video, max(0, self.resume - rewind)
        raise NoVideos


def main():
    """jwb-offline"""

    parser = argparse.ArgumentParser(prog='jwb-offline',
                                     usage='%(prog)s -d [DIR] -- COMMAND [ARGS]',
                                     description='Shuffle and play videos in DIR')
    parser.add_argument('--dir', '-d', metavar='DIR', default='.',
                        help='video directory')
    parser.add_argument('--replay-sec', metavar='SEC', type=int, default=30,
                        help='seconds to replay when resuming a video')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='show video player output')
    parser.add_argument('cmd', metavar='COMMAND', nargs='+',
                        help='video player command, "{}" gets replaced by starting position in secs')

    args = parser.parse_args()
    dir = Path(args.dir)
    cmd_output = None if args.verbose else subprocess.DEVNULL

    info = RuntimeInfo.load(dir / 'history.json')
    show_wait_msg = True

    # Save info before exit
    try:
        while True:
            videos = [v for v in dir.iterdir() if v.is_mp4()]

            # Wait for videos
            if not videos:
                if show_wait_msg:
                    msg('no videos to play yet')
                    show_wait_msg = False
                time.sleep(10)
                continue
            show_wait_msg = True

            try:
                # Resume if possible
                video, resume_pos = info.get_resume(dir, rewind=args.replay_sec)

            except NoVideos:
                while True:
                    try:
                        # Find a random video that wasn't played recently
                        video = random.choice([v for v in videos if v.name not in info.history])
                        resume_pos = 0
                        break
                    # Raised by choice if list is empty
                    except IndexError:
                        if info.history:
                            # Remove the oldest 20 history entries and try again
                            info.history = info.history[20:]
                        else:
                            # This can never happen as long as videos is non-empty
                            raise RuntimeError

            msg('playing: ' + video.name)
            info.register_start(video.name)
            subprocess.call([arg.replace('{}', str(resume_pos)) for arg in args.cmd] + [str(video)],
                            stdout=cmd_output, stderr=cmd_output)
            info.register_stop()

    finally:
        info.save(dir / 'history.json')


if __name__ == '__main__':
    main()
