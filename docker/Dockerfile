FROM python:3-bullseye

LABEL maintainer="Didstopia <support@didstopia.com>"

ENV DEBIAN_FRONTEND=noninteractive

# Set the working directory
WORKDIR /usr/src/app

# Install the necessary dependencies
# RUN apt update && \
#     apt install -y --no-install-recommends \
#       reprepro \
#       gpg \
#       python3 \
#       python3-git \
#       python3-gnupg \
#       expect \
#       python3-debian

# Install the necessary dependencies
RUN apt update && \
    apt install -y --no-install-recommends \
      expect \
      gpg \
      reprepro
      # python3 \
      # python3-git \
      # python3-gnupg \
      # python3-debian

# Copy the necessary Python scripts
# COPY entrypoint.py /entrypoint.py
# COPY key.py /key.py

# Install Python dependencies
ADD requirements.txt /usr/src/app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the necessary Python scripts
ADD entrypoint.py /usr/src/app/entrypoint.py
ADD key.py /usr/src/app/key.py

# Setup the startup script
# ENTRYPOINT [ "python3", "/entrypoint.py" ]
# CMD [ "python", "entrypoint.py" ]
CMD [ "python", "/usr/src/app/entrypoint.py" ]
