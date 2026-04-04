import os


def get_token_from_env(env_key: str) -> str:
    token = os.getenv(env_key, "").strip()
    if not token:
        raise RuntimeError(f"Missing required token env var: {env_key}")
    return token
