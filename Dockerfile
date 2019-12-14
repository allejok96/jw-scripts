FROM python:3

COPY jwlib /jwlib
COPY jwb-import /jwb-import
COPY jwb-index /jwb-index
COPY jwb-rpi /jwb-rpi
COPY jwb-stream /jwb-stream
COPY nwt-index /nwt-index

ADD setup.py /

RUN pip install setuptools
RUN [ "python", "setup.py", "install" ]

ENTRYPOINT ["/bin/bash"]
