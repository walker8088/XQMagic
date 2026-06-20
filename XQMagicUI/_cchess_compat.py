# -*- coding: utf-8 -*-
"""cchess API 兼容垫片.

cchess 1.26.x 重构移除了多个旧 API,但 XQMagicUI 大量代码仍按旧 API 编写
(尚未完成迁移). 为避免一次性大规模改动, 这里以 monkey-patch 方式恢复旧名.

恢复的符号:
- ``cchess.RED``          → ``cchess.SIDE_RED``
- ``cchess.BLACK``        → ``cchess.SIDE_BLACK``
- ``ChessBoard.get_move_color`` → 返回 ``move_side()`` 的结果
- ``ChessBoard.move_player``   → 轻量属性对象, 代理 ``move_side`` 的读写,
                                 并提供 ``next()`` / ``__eq__`` 兼容原 ``ChessPlayer``

垫片是幂等的: 重复 import 不会重复打补丁 (cchess 已包含的符号就跳过).
"""

import cchess
from cchess import SIDE_BLACK, SIDE_RED, ChessBoard

# ---- 颜色常量别名 ---------------------------------------------------
for _alias, _target in (("RED", SIDE_RED), ("BLACK", SIDE_BLACK)):
    if not hasattr(cchess, _alias):
        setattr(cchess, _alias, _target)


# ---- 模块级 ``cchess.get_move_color(fen)`` -----------------------
# 旧 cchess 在模块顶部提供 ``get_move_color(fen)`` 函数; 新版
# 改为 ``cchess.common.fen_move_color(fen)``, 顶层 import 不再可见。
# 在这里补别名。
if not hasattr(cchess, "get_move_color"):
    from cchess.common import fen_move_color as get_move_color  # noqa: E402

    cchess.get_move_color = get_move_color


# ---- ChessBoard.get_move_color / move_player -----------------------
if not hasattr(ChessBoard, "get_move_color"):
    ChessBoard.get_move_color = lambda self: self.move_side()


# ---- ChessBoard.is_valid_iccs_move -------------------------------
# 旧 API 直接提供 ``is_valid_iccs_move(iccs_str)``。新 cchess 仅有
# ``is_valid_move(from, to)``, 这里桥接一下。
if not hasattr(ChessBoard, "is_valid_iccs_move"):
    from cchess import iccs2pos as _iccs2pos

    def _is_valid_iccs_move(self, iccs):
        try:
            p_from, p_to = _iccs2pos(iccs)
        except Exception:
            return False
        return self.is_valid_move(p_from, p_to)

    ChessBoard.is_valid_iccs_move = _is_valid_iccs_move


# ---- ChessBoard.get_pieces / get_piece -----------------------------
class _PieceShim:
    """``ChessBoard.get_pieces()`` / ``get_piece(pos)`` 的轻量代理.

    旧 cchess 返回 ``Piece`` 对象 (含 ``.x`` / ``.y`` / ``.fench`` / ``.color``
    / ``.get_color_fench()``), 现在只剩 ``get_all_fench_positions()`` 产
    ``(fench, pos)`` 元组。这里包一层让 XQMagicUI 现有调用继续可用。
    """

    __slots__ = ("fench", "x", "y")

    def __init__(self, fench, x, y):
        self.fench = fench
        self.x = x
        self.y = y

    @property
    def color(self):
        # 兼容旧 ``piece.color``: 返回 SIDE_RED / SIDE_BLACK
        return SIDE_BLACK if self.fench.islower() else SIDE_RED

    def get_color_fench(self):
        # 旧 API 返回 ``"rk"`` / ``"bk"`` 形式 (用于 ``pieces_img`` key)
        # 黑方 fench 小写 → 前缀 b + 原 fench
        # 红方 fench 大写 → 前缀 r + 小写 fench
        if self.fench.islower():
            return f"b{self.fench}"
        return f"r{self.fench.lower()}"


if not hasattr(ChessBoard, "get_pieces"):
    ChessBoard.get_pieces = lambda self: [
        _PieceShim(f, x, y) for f, (x, y) in self.get_all_fench_positions()
    ]


if not hasattr(ChessBoard, "get_piece"):

    def _get_piece(self, pos):
        fench = self.get_fench(pos)
        if fench == ".":
            return None
        return _PieceShim(fench, pos[0], pos[1])

    ChessBoard.get_piece = _get_piece


if not hasattr(ChessBoard, "get_fenchs"):
    ChessBoard.get_fenchs = lambda self, fench: list(self.get_fench_positions(fench))


# ---- ChessBoard.move / move_iccs (保持旧 API 语义) ----------------
# 旧 cchess 中 ``move()`` / ``move_iccs()`` 不自动切走子方, 调用方需手动
# ``next_turn()``。新 cchess 1.26.x 在内部 ``move()`` 中切了走子方, 造成
# XQMagicUI 里 ``move_iccs(...) + next_turn()`` 的组合多重切换、导致
# 之后走法颜色错位。这里重包一层, 在调用 cchess 原生方法后把 move_side
# 改回去, 使调用方语义与旧版一致。
if hasattr(ChessBoard, "move") and hasattr(ChessBoard, "move_iccs"):
    _orig_move = ChessBoard.move
    _orig_move_iccs = ChessBoard.move_iccs

    def _compat_move(self, pos_from, pos_to, check=True):
        prev_side = self._move_side
        result = _orig_move(self, pos_from, pos_to, check)
        # 恢复走子方: 仅在走法有效时; 吃将/帅的情况不恢复 (局已结束)
        if result is not None and getattr(result, "move_info", None) is not None:
            captured = result.move_info.captured_fench
            if captured not in ("k", "K"):
                self._move_side = prev_side
        return result

    def _compat_move_iccs(self, move_str, check=True):
        prev_side = self._move_side
        result = _orig_move_iccs(self, move_str, check)
        if result is not None and getattr(result, "move_info", None) is not None:
            captured = result.move_info.captured_fench
            if captured not in ("k", "K"):
                self._move_side = prev_side
        return result

    ChessBoard.move = _compat_move
    ChessBoard.move_iccs = _compat_move_iccs


# ---- Move.board_done (兼容旧 cchess 字段名) -----------------------
# 旧 cchess 的 Move 有 board_done (走子后的棋盘)。新 cchess 改为
# board_after。XQMagicUI 多处使用 board_done。
from cchess import Move as _CchessMove  # noqa: E402

if not hasattr(_CchessMove, "board_done"):
    _CchessMove.board_done = property(lambda self: self.board_after)


# ---- Move.board (兼容旧 cchess 字段名) ----------------------------
# 旧 cchess ``Move.board`` 指向走子后的棋盘; 新版改为 ``board_after``。
# XQMagicUI 多处使用 ``move.board.to_fen()`` / ``move.board.move_player``。
if not hasattr(_CchessMove, "board"):
    _CchessMove.board = property(lambda self: self.board_after)


# ---- Move.p_from / p_to (兼容旧 cchess 字段名) --------------------
# 旧 cchess Move 有 ``p_from`` / ``p_to``; 新版改为 ``pos_from`` / ``pos_to``。
if not hasattr(_CchessMove, "p_from"):
    _CchessMove.p_from = property(lambda self: self.pos_from)
if not hasattr(_CchessMove, "p_to"):
    _CchessMove.p_to = property(lambda self: self.pos_to)


# ---- ChessBoard.set_move_color / set_move_side 别名 ----------------
# 旧 API 调用 ``set_move_color``; 新版改为 ``set_move_side``。
if not hasattr(ChessBoard, "set_move_color"):
    ChessBoard.set_move_color = lambda self, color: self.set_move_side(color)


class _MovePlayerShim:
    """``ChessBoard.move_player`` 的属性代理.

    旧 cchess 用 ``ChessPlayer`` 对象 (含 .color / .next() / ``==``),
    现在 ``ChessBoard`` 只剩 ``move_side()`` / ``set_move_side()``.
    这里用一个轻量 wrapper 把两者粘起来, XQMagicUI 现有代码无需修改.
    """

    __slots__ = ("_board",)

    def __init__(self, board):
        self._board = board

    @property
    def color(self):
        return self._board.move_side()

    @color.setter
    def color(self, value):
        self._board.set_move_side(value)

    def next(self):
        current = self._board.move_side()
        self._board.set_move_side(SIDE_BLACK if current == SIDE_RED else SIDE_RED)
        return self.color

    def __eq__(self, other):
        if other is None:
            return False
        other_color = getattr(other, "color", other)
        return self.color == other_color

    def __repr__(self):
        return f"MovePlayer(color={self.color})"


if not hasattr(ChessBoard, "move_player"):

    def _get_move_player(self):
        # 每次返回新 shim,避免外部缓存的旧状态
        return _MovePlayerShim(self)

    ChessBoard.move_player = property(_get_move_player)
