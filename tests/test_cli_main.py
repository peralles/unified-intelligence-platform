from integrator.cli.main import _build_parser


def test_parser_has_core_commands():
    parser = _build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    assert {"status", "login", "accounts", "use", "logout", "tools", "serve"}.issubset(
        set(sub.choices.keys())
    )
