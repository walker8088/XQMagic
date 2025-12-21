def test_piece_name_conversions():
    from MagicUI.BoardWidgets import piece_name_to_fench, fench_to_piece_name
    assert piece_name_to_fench("rk") == "K"
    assert fench_to_piece_name("k") == "bk"
    assert fench_to_piece_name("K") == "rk"

