FROM public.ecr.aws/lambda/python:3.12

# 1. Install System Dependencies (Added flac for potential audio captcha)
RUN dnf install -y \
    atk cups-libs gtk3 libXcomposite alsa-lib \
    libXcursor libXdamage libXext libXi libXrandr libXScrnSaver \
    libXtst pango at-spi2-atk libXt xorg-x11-server-Xvfb \
    xorg-x11-xauth dbus-glib nss mesa-libgbm jq unzip \
    wget tar xz procps-ng mesa-libEGL libxkbcommon nodejs

# 2. Install Chrome
RUN wget https://storage.googleapis.com/chrome-for-testing-public/121.0.6167.85/linux64/chrome-linux64.zip && \
    unzip chrome-linux64.zip -d /opt/ && \
    rm chrome-linux64.zip

# 3. Install ffmpeg static binary
RUN wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz && \
    tar -xf ffmpeg-release-amd64-static.tar.xz && \
    mv ffmpeg-*-static/ffmpeg /usr/bin/ && \
    mv ffmpeg-*-static/ffprobe /usr/bin/ && \
    rm -rf ffmpeg-release-amd64-static.tar.xz ffmpeg-*-static

# 4. Setup Working Directory
WORKDIR ${LAMBDA_TASK_ROOT}
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy Code
COPY . .

# 6. Playwright Environment Variables
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV HOME=/tmp
ENV XDG_RUNTIME_DIR=/tmp

# Ensure /tmp is clean and writable
RUN rm -rf /tmp/* && chmod 1777 /tmp

# Default CMD is for the Flask App (linkedin_to_whatsapp.py)
# Note: SAM overrides this for the WorkerFunction using ImageConfig
CMD [ "LinkedIn_to_WhatsApp.handler" ]