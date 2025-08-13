#!/usr/bin/env bash
set -o errexit

# Устанавливаем ffmpeg для генерации кружков с голосом
apt-get update
apt-get install -y ffmpeg

# Устанавливаем Python-зависимости
pip install --upgrade pip
pip install -r requirements.txt
