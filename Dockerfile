FROM python:3.11.0b3-slim

COPY jwlib /jwlib
COPY jwb-index /jwb-index
COPY jwb-offline /jwb-offline

ADD setup.py /

RUN pip install setuptools
RUN [ "python", "setup.py", "install" ]

ENTRYPOINT ["/bin/bash"]
