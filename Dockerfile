FROM python:3

COPY jwlib /jwlib
COPY jwb-index /jwb-index
COPY jwb-stream /jwb-stream
COPY jwb-offline /jwb-offline
COPY jwb-offline-import /jwb-offline-import

ADD setup.py /

RUN pip install setuptools
RUN [ "python", "setup.py", "install" ]

ENTRYPOINT ["/bin/bash"]
