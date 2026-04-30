from pathlib import Path

from flask import Flask

from app.config import APP_NAME, APP_VERSION, PORT
from app.routes import routes_bp

_BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(_BASE_DIR / 'templates'),
    static_folder=str(_BASE_DIR / 'static'),
    static_url_path='/static',
)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB upload limit
app.register_blueprint(routes_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
