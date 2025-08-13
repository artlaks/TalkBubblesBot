#!/usr/bin/env bash
set -o errexit  # прерывать при ошибках

pip install --upgrade pip setuptools wheel
pip install -r requirements.txt --prefer-binary
