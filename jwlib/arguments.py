valid_args = {
    '--quiet': {'action': 'count'},
    '--mode': {
        'default': 'stdout',
        'choices': ['stdout', 'filesystem', 'm3u', 'm3ucompat', 'html'],
        'help': 'output mode',
        'dest': '_mode'},
    '--lang': {
        'nargs': '?',
        'default': 'E',
        'help': 'language code'},
    '--download': {
        'action': 'store_true',
        'help': 'download media'},
    '--limit-rate': {
        'default': '1M',
        'dest': 'rate_limit'},
    '--category': {
        'default': 'VideoOnDemand',
        'dest': 'category',
        'help': 'category/section to index'},
    '--latest': {
        'action': 'store_const',
        'const': 'LatestVideos',
        'dest': 'category'},
    '--quality': {
        'default': 720,
        'type': int,
        'choices': [240, 360, 480, 720],
        'help': 'maximum video quality'},
    '--subtitles': {'action': 'store_true'},
    '--no-subtitles': {
        'action': 'store_false',
        'dest': 'subtitles',
        'help': 'prefer un-subtitled videos'},
    '--since': {
        'metavar': 'YYYY-MM-DD'},
    '--checksum': {
        'action': 'store_true',
        'dest': 'checksums',
        'help': 'check md5 checksum'},
    '--no-checksum': {
        'action': 'store_false',
        'help': 'check md5 checksum'},
    '_work_dir': {
        'nargs': '?',
        'default': '.',
        'metavar': 'DIR',
        'help': 'directory to save data in'}}


def add_arguments(parser, selected_args=None):
    if not selected_args:
        selected_args = valid_args.keys()

    for arg in selected_args:
        parser.add_argument(arg, **valid_args[arg])
