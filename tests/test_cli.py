from formula1_strategy_tool.cli import main


def test_main_runs(capsys):
    main([])
    captured = capsys.readouterr()
    assert "Formula 1 Live Strategy Tool" in captured.out
