import json

from jinja2 import Environment, FileSystemLoader, select_autoescape

templates = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html"]),
)

templates.filters["tojson"] = lambda v: json.dumps(v, ensure_ascii=False)
