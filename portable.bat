rem  Open a command prompt and setup aliases for jwb-index and jwb-offline
start cmd.exe /K "set JWDIR=%CD%& doskey jwb-index=python %%JWDIR%%\jwb-index $*& doskey jwb-offline=python %%JWDIR%%\jwb-offline $*& echo Type jwb-index --help for more info"
