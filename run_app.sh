#!/usr/bin/env bash
uvicorn api_server.app.main:app --reload --host 0.0.0.0 --port 8000
