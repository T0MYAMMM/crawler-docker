#!/bin/bash

# Ensure log directory exists and has proper permissions
mkdir -p /var/log/crawler
chmod 777 /var/log/crawler

# Switch to scheduler user and start the scheduler
exec gosu scheduler "$@" 