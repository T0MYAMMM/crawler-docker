#!/bin/bash
# Deploy script for each server

SERVER_ID=$1
if [ -z "$SERVER_ID" ]; then
    echo "Usage: $0 <server_id>"
    exit 1
fi

# Create necessary directories
sudo mkdir -p /var/log/crawler
sudo mkdir -p /opt/crawler
sudo chown -R $USER:$USER /var/log/crawler /opt/crawler

# Install Python dependencies
pip install -r requirements.txt

# Copy application files
cp -r . /opt/crawler/

# Create systemd service
sudo tee /etc/systemd/system/crawler-server-${SERVER_ID}.service > /dev/null <<EOF
[Unit]
Description=ONM Crawler Server ${SERVER_ID}
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/crawler
ExecStart=/usr/bin/python3 worker_manager.py --server-id ${SERVER_ID} --workers 3
Restart=always
RestartSec=10
Environment=PYTHONPATH=/opt/crawler

[Install]
WantedBy=multi-user.target
EOF

# Create log rotation
sudo tee /etc/logrotate.d/crawler > /dev/null <<EOF
/var/log/crawler/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 $USER $USER
}
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable crawler-server-${SERVER_ID}
sudo systemctl start crawler-server-${SERVER_ID}

echo "Crawler server ${SERVER_ID} deployed and started"