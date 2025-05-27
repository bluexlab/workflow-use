FROM node:22

# RUN apt-get update && \
#     apt-get install -y python3 && \
#     npm install --global some-node-package

RUN apt-get update && \
	apt-get install -y python3 && \
	apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh
# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh
# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

RUN mkdir /app
WORKDIR /app
COPY extension /app/extension
COPY ui /app/ui
COPY workflows /app/workflows
COPY static /app/static

# Build Browser Extension
WORKDIR /app/extension
RUN npm install
RUN npm run build

WORKDIR /app/workflows
RUN uv sync
RUN . .venv/bin/activate
ENV PATH="/app/workflows/.venv/bin:$PATH"
RUN playwright install-deps chromium
RUN playwright install chromium
