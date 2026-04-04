import subprocess
from pathlib import Path
from typing import Callable


class CommandError(RuntimeError):
    def __init__(self, message: str, stdout: str = "", stderr: str = "", returncode: int | None = None):
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def run(
    command,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = True,
    env: dict | None = None,
    live: bool = False,
    line_callback: Callable[[str], None] | None = None,
):
    if not live:
        r = subprocess.run(list(command), cwd=str(cwd) if cwd else None, text=True, capture_output=capture, env=env)
        if check and r.returncode != 0:
            raise CommandError(
                f"Command failed: {' '.join(command)}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}",
                stdout=r.stdout,
                stderr=r.stderr,
                returncode=r.returncode,
            )
        return r

    process = subprocess.Popen(
        list(command),
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        env=env,
    )
    lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        lines.append(line)
        print(line, end="", flush=True)
        if line_callback is not None:
            line_callback(line)
    process.wait()
    stdout = ''.join(lines)
    stderr = ''
    if check and process.returncode != 0:
        raise CommandError(
            f"Command failed: {' '.join(command)}\nstdout:\n{stdout}\nstderr:\n{stderr}",
            stdout=stdout,
            stderr=stderr,
            returncode=process.returncode,
        )
    return subprocess.CompletedProcess(list(command), process.returncode, stdout=stdout if capture else '', stderr=stderr)


def sudo_write_file(path: Path, content: str):
    r = subprocess.run(["sudo", "tee", str(path)], input=content, text=True, capture_output=True)
    if r.returncode != 0:
        raise CommandError(f"Failed writing {path}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}", stdout=r.stdout, stderr=r.stderr, returncode=r.returncode)


def is_port_listening(port: int) -> bool:
    r = subprocess.run(["ss", "-lntp"], text=True, capture_output=True)
    return f":{port} " in r.stdout or f":{port}\n" in r.stdout


def docker_root() -> str:
    r = subprocess.run(["docker", "info", "--format", "{{.DockerRootDir}}"], text=True, capture_output=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def docker_healthy() -> bool:
    return subprocess.run(["docker", "info"], text=True, capture_output=True).returncode == 0
