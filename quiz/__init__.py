from flask import Blueprint

quiz_bp = Blueprint(
    "quiz",
    __name__,
    url_prefix="/quiz",
    template_folder="templates",
    static_folder="static",
)

from . import routes  # noqa: E402,F401 (register routes)
