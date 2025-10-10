FROM python:3.11-slim

LABEL authors="FOI-Bioinformatics" \
      description="Container for taxpasta_to_bioboxes script with pandas and ete3"

# Install system dependencies required by ete3
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        wget \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    pandas>=2.0 \
    ete3>=3.1.3

# Verify installations
RUN python -c "import pandas; import ete3; print('pandas:', pandas.__version__); print('ete3:', ete3.__version__)"

# Set working directory
WORKDIR /data

CMD ["/bin/bash"]
