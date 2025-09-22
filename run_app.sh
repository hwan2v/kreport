#!/usr/bin/env bash
cp config/local.env .env
uvicorn api_server.app.main:app --reload --host 0.0.0.0 --port 8000
