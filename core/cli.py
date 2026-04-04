
import typer
from homelab_os.core.plugin_manager.installer import PluginInstaller

app = typer.Typer()

@app.command()
def install_plugin(plugin_archive: str):
    installer = PluginInstaller()
    result = installer.install_plugin(plugin_archive)
    print(result)

@app.command()
def bootstrap_host():
    print("Host bootstrap done")

if __name__ == "__main__":
    app()
