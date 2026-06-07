# EngineManager stop-wait-go 同步机制

## 问题背景

在 UCI/UCCI 协议中，向引擎发送 `stop` 命令后，引擎会返回 `bestmove` 来确认已停止。
在引擎返回 `bestmove` 之前，不应发送新的 `go` 命令，否则可能导致引擎状态混乱。

但在 XQMagic 中，用户快速走子时会频繁调用 `goFrom()`，如果每次都直接发送 stop + go，
连续走子时 stop/go 命令交织，引擎可能无法正确响应。

## 方案演进

### 方案 1：最初方案（直接发送）
```python
def stopThinking(self):
    self.engine.stop_thinking()  # 发送 stop，立即返回

def goFrom(self, ...):
    self.stopThinking()
    return self.engine.go_from(fen_engine, params)  # 立即发送 go
```
**问题**：连续走子时 stop/go 命令交织，引擎状态混乱。

### 方案 2：主线程阻塞等待（❌ 失败）
```python
def stopThinking(self):
    self.engine.stop_thinking()
    self._stop_event.wait(timeout=3.0)  # 阻塞主线程等待 bestmove
```
**问题**：`goFrom()` 从主线程（UI线程）调用，`wait()` 阻塞导致页面卡顿。

**教训**：任何等待引擎响应的逻辑必须在引擎线程中执行，不能阻塞主线程。

### 方案 3：引擎线程等待（❌ 失败）
```python
def goFrom(self, ...):
    self._pending_go = (fen_engine, fen, params)
    self._stop_requested = True
    self.engine.stop_thinking()  # 只发 stop，不发 go

# _runOnce 中收到 bestmove 后才发送 pending 的 go
```
**问题**：等待 stop 响应期间，`_runOnce` 直接 return 忽略了 info_move，
用户看不到任何引擎输出，以为引擎死了。

### 方案 4：最终方案 ✅

核心改进：等待 stop 响应期间，**继续处理 info_move**，保持引擎进度可见。

```python
def goFrom(self, ...):
    if not self._is_analyzing:
        # 引擎空闲，直接发送 go
        self._is_analyzing = True
        return self.engine.go_from(fen_engine, params)
    
    # 引擎正在分析，设置 pending + 发送 stop
    self._pending_go = (fen_engine, fen, params)
    self._stop_requested = True
    self.engine.stop_thinking()

def _runOnce(self):
    if self._stop_requested:
        if act_id == "bestmove":
            # stop 响应到了，发送 pending 的 go
            self._stop_requested = False
            self._is_analyzing = False
            if self._pending_go:
                ...
                self._is_analyzing = True
                self.engine.go_from(fen_engine, params)
            return  # 只拦截 bestmove
        # info_move 等继续正常处理，不 return
    
    # 正常处理 bestmove/info_move...
```

## 流程说明

```
用户走子 A → goFrom(A) → _is_analyzing=False → 直接发送 go(A)
  └─ _is_analyzing = True

用户走子 B → goFrom(B) → _is_analyzing=True → 设置 pending=B + 发送 stop
  └─ _runOnce 收到 info_move(A) → 正常处理 → 用户看到引擎进度
  └─ _runOnce 收到 info_move(A) → 正常处理 → 用户看到引擎进度
  └─ _runOnce 收到 bestmove(A) → 拦截 → 发送 go(B) → _is_analyzing=True

用户走子 C → goFrom(C) → _is_analyzing=True → pending 被覆盖为 C + 发送 stop
  └─ _runOnce 收到 info_move(B) → 正常处理 → 用户看到引擎进度
  └─ _runOnce 收到 bestmove(B) → 拦截 → 发送 go(C) → _is_analyzing=True

分析完成 → _runOnce 收到 bestmove(C)
  └─ _stop_requested=False → 正常处理 → 发出信号到 MainWindow
```

## 关键属性

| 属性 | 说明 |
|------|------|
| `_pending_go` | 存储待发送的 go 命令 `(fen_engine, fen, params)` |
| `_stop_requested` | 标记是否正在等待 stop 完成 |
| `_is_analyzing` | 标记引擎是否正在分析中 |

## 注意事项

1. **新命令覆盖旧命令是正确行为**：用户切换到新局面时，旧局面分析请求应被丢弃
2. **stop 命令是幂等的**：连续发送多次 stop 不会有问题
3. **info_move 持续输出**：等待 stop 响应期间用户能看到引擎进度，不会以为引擎死了
4. **redoThinking 也使用 pending 机制**：确保一致性
5. **首次 goFrom 直接发送**：`_is_analyzing=False` 时引擎空闲，无需等待 stop
6. **后台队列被跳过时必须继续调度**：`processNextBgPosition()` 弹出队列后，如果该任务未真正启动且未进入 pending，必须立刻调度下一个任务，否则后台补全会中断，表现为后续局面分数为空

## 后台补全补丁（2025-05）

在 `Main.py::processNextBgPosition()` 中新增了“跳过任务续跑”判断：

- 调用 `goFrom()` 后检查该任务是否真的启动（`_is_analyzing + isBackgroundMode`）
- 或已进入 `EngineManager._pending_go`（等待 stop 后启动）
- 若两者都不满足，说明该后台任务被跳过，立即 `QTimer.singleShot(0, self.processNextBgPosition)` 继续处理队列

这样可以保证：**即使中间某个后台任务被忽略，后续任务仍会继续补全，不会出现历史局面分数长期空白**。

## 相关文件

- `XQMagicUI/Engine.py` - EngineManager 实现
- `XQMagicUI/Main.py` - MainWindow 调用 goFrom
