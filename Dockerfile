FROM python:3.12

ARG WORKDIR=/app

# Set working directory
RUN mkdir -p ${WORKDIR}
WORKDIR ${WORKDIR}

# Install uv
RUN pip install --upgrade pip
RUN pip install uv

# Copy uv.lock and pyproject.toml
COPY pyproject.toml uv.lock ${WORKDIR}

# Install dependencies
RUN uv sync --no-dev

# Copy files
COPY ./build_with_ai ${WORKDIR}/build_with_ai

# Start command
CMD ["uv", "run", "python", "-m", "build_with_ai.app"]
