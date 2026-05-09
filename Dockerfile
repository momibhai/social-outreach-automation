FROM python:3.10-slim

# Install system dependencies, Google Chrome, and Xvfb
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    xvfb \
    curl \
    && mkdir -p /etc/apt/keyrings \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
RUN pip install --no-cache-dir streamlit seleniumbase gspread google-auth openai python-dotenv pytz pandas

# Copy application files
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Create an entrypoint script
RUN echo '#!/bin/bash\n\
# Start Streamlit in the background or foreground\n\
streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Run the entrypoint
CMD ["/app/entrypoint.sh"]
