"""Read-only discovery, state and consumption example."""

if __name__ == "__main__":
    if __package__:
        from .diagnostics import cli
    else:
        from diagnostics import cli

    raise SystemExit(cli("api"))
