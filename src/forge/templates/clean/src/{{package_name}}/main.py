from __future__ import annotations
from flask import Flask
from .shared.config import Settings
from .shared.logging import configure_logging
from .shared.di import Container
from .shared.di_wiring import register_core, register_features
from .interfaces.http.api import build_api_blueprint, register_http

def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or Settings()
    configure_logging("DEBUG" if settings.app_env == "development" else "INFO")

    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.secret_key

    # DI container
    container = Container()
    register_core(container, settings)   # db/session, common providers
    register_features(container)         # per-feature providers

    # HTTP
    api_bp = build_api_blueprint()
    register_http(app, api_bp=api_bp, container=container)

    @app.get("/health")
    def health():
        return {"status": "ok"}, 200

    return app

if __name__ == "__main__":
    settings = Settings()
    app = create_app(settings)
    app.run(host="0.0.0.0", port=settings.port, debug=(settings.app_env == "development"))