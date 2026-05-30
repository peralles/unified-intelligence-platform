from integrator.cli.main import _build_parser


def test_parser_bootstrap_only():
    parser = _build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    assert set(sub.choices.keys()) == {"init", "serve", "serve-http", "service"}
