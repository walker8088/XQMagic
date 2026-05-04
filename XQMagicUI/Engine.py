# -*- coding: utf-8 -*-

import logging
import time

import cchess
from cchess import ChessBoard, UcciEngine, UciEngine

# import threading
from PyQt5.QtCore import QObject, pyqtSignal

from .Utils import MATE_SCORE, ThreadRunner


# -----------------------------------------------------#
class EngineManager(QObject):
    readySignal = pyqtSignal(int, str, list)
    moveBestSignal = pyqtSignal(int, dict)
    moveInfoSignal = pyqtSignal(int, dict)
    checkmateSignal = pyqtSignal(int, dict)
    drawSignal = pyqtSignal(int, dict)

    def __init__(self, parent, id):
        super().__init__()

        self.id = id
        self.parent = parent

        self.options = {}

        self.fen = None
        self.fen_engine = None

        self.isRunning = False
        self.isReady = False

        # 后台思考相关
        self.isBackgroundMode = False

        # stop-wait-go 异步同步机制
        self._pending_go = None  # (fen_engine, fen, params)
        self._stop_requested = False  # 是否正在等待 stop 完成
        self._is_analyzing = False  # 引擎是否正在分析中

    def loadEngine(self, engine_path, engine_type):
        if engine_type == "uci":
            engine = UciEngine("")
        elif engine_type == "ucci":
            engine = UcciEngine("")
        else:
            raise Exception("目前只支持[uci, ucci]类型的引擎。")

        if engine.load(engine_path):
            self.engine = engine
            return True
        else:
            return False

    def setOption(self, name, value):
        self.options[name] = value

        if not self.isReady:
            return False

        logging.info(f"Engine[{self.id}] setOption: {name} = {value}")
        self.engine.set_option(name, value)

        return True

    def goFrom(self, fen_engine, fen=None, params={}):
        if not self.isReady:
            return False

        if not fen:
            fen = fen_engine

        # 跳过不合理的fen,免得引擎误报
        if (cchess.EMPTY_BOARD in fen_engine) or (cchess.EMPTY_BOARD in fen):
            return False

        # 如果引擎空闲，直接发送 go
        if not self._is_analyzing:
            self.fen_engine = fen_engine
            self.fen = fen
            self.params = params
            self.isBackgroundMode = params.get("_is_background", False)
            self._is_analyzing = True
            logging.info(f"Engine[{self.id}] go: {self.fen_engine} {self.params}")
            return self.engine.go_from(fen_engine, params)

        # 引擎正在分析，设置 pending，等待 stop 完成后发送
        self._pending_go = (fen_engine, fen, params)
        self._stop_requested = True
        self.engine.stop_thinking()

        logging.info(f"Engine[{self.id}] go pending: {self.fen_engine}")
        return True

    def stopThinking(self):
        if not self.isReady:
            return True

        logging.info(f"Engine[{self.id}] stop")
        self.engine.stop_thinking()
        # time.sleep(0.2)
        # self.engine.get_action()

        return True

    def redoThinking(self):
        if self.fen_engine:
            # 使用 pending 机制，确保 stop 完成后再发送 go
            self._pending_go = (self.fen_engine, self.fen, self.params)
            self._stop_requested = True
            self.engine.stop_thinking()
            logging.info(f"Engine[{self.id}] redo pending: {self.fen_engine}")

    def start(self):
        self.thread = ThreadRunner(self)
        self.thread.start()

    def stop(self):
        self.isRunning = False

    def quit(self):
        if not self.isReady:
            return

        self.stop()
        time.sleep(0.2)
        self.engine.quit()
        logging.info(f"Engine[{self.id}] quit.")

    def run(self):
        self.isRunning = True
        while self.isRunning:
            try:
                self._runOnce()
            except Exception as e:
                logging.error(str(e))
            time.sleep(0.1)
        # self.engine.stop_thinking()

    def _runOnce(self):
        action = self.engine.get_action()
        if action is None:
            return

        act_id = action["action"]

        if act_id == "ready":
            self.isReady = True
            self.readySignal.emit(self.id, self.engine.ids["name"], self.engine.options)
            return

        # 如果正在等待 stop 完成，拦截 bestmove，但继续处理 info_move
        if self._stop_requested:
            if act_id == "bestmove":
                self._stop_requested = False
                self._is_analyzing = False  # 旧分析已停止
                if self._pending_go:
                    fen_engine, fen, params = self._pending_go
                    self._pending_go = None
                    self.fen_engine = fen_engine
                    self.fen = fen
                    self.params = params
                    self.isBackgroundMode = params.get("_is_background", False)
                    self._is_analyzing = True  # 新分析开始
                    logging.info(
                        f"Engine[{self.id}] go: {self.fen_engine} {self.params}"
                    )
                    self.engine.go_from(fen_engine, params)
                return  # 只拦截 bestmove
            # info_move 等继续正常处理，不 return
            # 用户在等待 stop 响应期间仍能看到引擎进度

        # move_color = cchess.get_move_color(self.fen)
        board = None
        move_color = cchess.RED  # 默认值
        if self.fen:
            action["fen"] = self.fen
            board = ChessBoard(self.fen)
            move_color = board.get_move_color()

        if act_id == "bestmove":
            ret = {}
            ret.update(action)
            iccs = ret["iccs"] = ret.pop("move")

            # 确保有 board 对象才验证着法
            if board is not None:
                m = board.copy().move_iccs(iccs)
                # 引擎有时会输出以前的局面的着法，这里预先验证一下能不能走，不能走的着法都忽略掉
                if m is None:
                    return
            else:
                # 没有 fen 信息时创建临时 board 来验证
                board = ChessBoard()
                m = board.copy().move_iccs(iccs)
                if m is None:
                    return

            # 分数换算到红方得分
            if move_color == cchess.BLACK:
                for key in ["score", "mate"]:
                    if key in ret:
                        ret[key] = -ret[key]

            # 再处理出现mate时，score没分的情况
            if "mate" in ret:
                mate_flag = 1 if ret["mate"] > 0 else -1
                ret["score"] = MATE_SCORE * mate_flag

            new_fen = board.to_fen() if board else ""
            iccs_dict = {"iccs": iccs, "new_fen": new_fen}
            for key in ["score", "mate"]:
                if key in ret:
                    iccs_dict[key] = ret[key]

            self._is_analyzing = False  # 分析完成
            ret["is_background"] = self.isBackgroundMode
            ret["actions"] = {iccs: iccs_dict}
            self.moveBestSignal.emit(self.id, ret)

        elif act_id == "info_move":
            action["color"] = move_color
            self.moveInfoSignal.emit(self.id, action)
        elif act_id == "dead":  # 引擎被将死
            self.checkmateSignal.emit(self.id, action)
        elif act_id == "draw":  # 引擎输出和棋
            self.drawSignal.emit(self.id, action)


# -----------------------------------------------------#
