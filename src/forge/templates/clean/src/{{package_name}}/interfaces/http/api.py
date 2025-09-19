# src/<pkg>/interfaces/http/api.py
from __future__ import annotations
from flask import Blueprint
from ...shared.di import Container

# [forge:auto-imports]  # <— generator inserts imports here

def build_api_blueprint() -> Blueprint:
    api = Blueprint("api", __name__, url_prefix="/api")
    # [forge:auto-register]  # <— generator inserts blueprint registrations here
    return api

def register_http(app, *, api_bp: Blueprint, container: Container) -> None:
    # [forge:auto-init]  # <— generator inserts controller init(container) here
    app.register_blueprint(api_bp)
