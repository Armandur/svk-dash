import json

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

templates = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html"]),
)

templates.filters["tojson"] = lambda v: Markup(json.dumps(v, ensure_ascii=False))
