# XQMagic - Agent Guide

## Project Overview

XQMagic (磁力象棋) is a Chinese Chess (Xiangqi) desktop application built with **Python + PyQt5**. It provides free practice, human-vs-engine challenges, endgame puzzles, and cloud database integration.

**Key tech stack:** PyQt5, cchess (chess logic library), Peewee ORM (SQLite), TinyDB, HTTP (cloud DB), UCI/UCCI engine protocol.

---

## Directory Structure

```
XQMagic/
├── XQMagic.py              # Entry point (5 lines)
├── XQMagic.ini             # App config (MainEngine section)
├── pyproject.toml          # Project metadata, Python >=3.11
├── requirments.txt         # Dependencies
├── XQMagicUI/              # Core UI package
│   ├── App.py              # ChessApp(QApplication), run()
│   ├── Main.py             # MainWindow (~1918 lines) - central orchestrator
│   ├── Widgets.py          # All dock widgets (~1848 lines)
│   ├── BoardWidgets.py     # Chess board rendering (~912 lines)
│   ├── CloudDB.py          # Cloud DB client (chessdb.cn)
│   ├── LocalDB.py          # Local SQLite databases (~827 lines)
│   ├── Engine.py           # UCI/UCCI engine manager
│   ├── Storage.py          # TinyDB storage (bookmarks, endbooks)
│   ├── Online.py           # Screen capture & board recognition
│   ├── Dialogs.py          # Dialog windows (~570 lines)
│   ├── Utils.py            # Enums, utilities, helpers (~391 lines)
│   ├── Globl.py            # Global state (fenCache, singletons)
│   ├── Ecco.py             # ECCO opening encyclopedia DLL wrapper
│   ├── Resource.py         # Compiled Qt resources
│   ├── SnippingWidget.py   # Screen snipping tool
│   └── Version.py          # Version string ('26.1')
├── Engine/                 # Chess engines (Pikafish, Eleeye, EccoDLL)
├── Game/                   # Runtime data (masterbook.db, localbook.db, endbooks.json)
├── Books/                  # Opening book collections
├── Skins/                  # Board skins
├── Sound/                  # Sound effects
├── ImgRes/                 # Image resources
├── Tools/                  # Utility scripts
└── Tests/                  # Test suite
```

---

## Application Flow

```
XQMagic.py
  └─> XQMagicUI.App.run()
        ├─ ChessApp(QApplication) created
        ├─ QSettings('XQSoft', 'XQMagic') initialized
        ├─ CLI args parsed (--debug, --clean, file)
        ├─ Global fonts set
        └─ MainWindow shown via showWin()
```

**MainWindow init flow:**
1. Create `QGameManager`, connect `game_mode_changed_signal`
2. Read `XQMagic.ini` config
3. Open databases: `MasterBook`, `EndBookStore`, `LocalBook`
4. Create `EngineManager` and `OnlineManager`
5. Create `ChessBoard` and all UI widgets
6. Set up dock widgets and connect signals
7. Load skins, sound, actions, menus, toolbars
8. Create `CloudDB`, connect `query_result_signal`
9. Switch to `GameMode.Free`, start engine thread

---

## Key Classes

### Data Structures

**Position dict** (passed throughout the app):
```python
{
    'fen': str,           # Full FEN string
    'fen_prev': str,      # FEN before the move
    'fen_engine': str,    # FEN formatted for engine
    'iccs': str,          # ICCS move notation (e.g., "h2e2")
    'move': Move,         # cchess Move object
    'index': int,         # Position index in game
    'move_color': int,    # cchess.RED or cchess.BLACK
    'view': [QStandardItem, ...],  # Table view items (for HistoryWidget)
    'ecco': str,          # Opening code
}
```

**Action dict** (move candidates):
```python
{
    'iccs': str,          # ICCS move
    'text': str,          # Chinese move text
    'score': int,         # Score (positive = red advantage)
    'diff': int,          # Difference from best score
    'new_fen': str,       # Resulting FEN
    'mark': str,          # Optional mark
    'memo': str,          # Optional memo
}
```

**fenCache** (`Globl.fenCache` - `defaultdict(dict)`):
Central cache mapping FEN -> `{score, score_e, diff, best_next, alter_best, fen_prev, ...}`
- `score` = cloud database score
- `score_e` = engine score
- `diff` = score difference from best move
- `best_next` = list of best ICCS moves

### Game Modes (`Utils.py`)

```python
class GameMode(Enum):
    Free = 1           # Free practice
    EngineAssit = 2    # Engine assistance
    EngineFight = 3    # Human vs engine
    EngineEndGame = 4  # Endgame puzzles
    EngineOnline = 5   # Online analysis

class ReviewMode(Enum):
    ByEngine = 1       # Engine review
    ByCloud = 2        # Cloud DB review
```

---

## UI Organization

### Central Widget
- **BoardPanelWidget** - contains `ChessBoardWidget` (visual board) + navigation toolbar

### Dock Widgets

| Widget | Area | Purpose |
|--------|------|---------|
| `HistoryWidget` (in `DockHistoryWidget`) | Right | Move list table with scores, annotations, branches |
| `EngineWidget` | Bottom | Engine controls, MultiPV analysis tree |
| `BoardActionsWidget` | Left | Best moves panel with "搜索云库" checkbox at top |
| `EndBookWidget` | Left | Endgame puzzle library |
| `BookmarkWidget` | Left | Saved positions/games |
| `GameLibWidget` | Left | Game library viewer |

### Key Layout Details

**HistoryWidget layout** (top to bottom):
1. `showScoreBox` (QCheckBox "分数")
2. `hsplitter` (horizontal: `posView` table | vertical splitter for annotations + branches)
3. Button row: "收藏棋谱" + "收藏局面"

**BoardActionsWidget layout** (top to bottom):
1. `queryCloudBox` (QCheckBox "搜索云库")
2. `actionsView` (QTreeWidget with columns: MK, 备选着法, 得分)

### Toolbars
- `File` - open, save, bookmarks
- `Game` - free practice, robot fight, endgame, restart, edit board
- `Show` - (reserved, currently minimal)
- `System` - exit

---

## Data Flow

### Move Execution Flow
```
User clicks board
  └─> ChessBoardWidget.mousePressEvent()
        └─> try_move() validates
              └─> tryMoveSignal.emit(from, to)
                    └─> MainWindow.onTryBoardMove()
                          └─> onMoveGo(iccs)
                                ├─ board.move_iccs()
                                ├─ Create position dict, append to positionList
                                ├─ Update fenCache[new_fen]
                                ├─ historyView.onNewPostion()  # adds row
                                ├─ updateStatus()  # sound, status bar
                                └─ changePositionSignal.emit()
                                      └─ onChangePosition()
                                            ├─ boardView.showMove()
                                            ├─ localSearch()  # query opening books
                                            ├─ cloudQuery.startQuery()  # if cloud mode
                                            └─ runEngine()  # if engine active
```

### Engine Output Flow
```
EngineManager._runOnce()
  ├─ 'bestmove' -> moveBestSignal -> MainWindow.onTryEngineMove()
  │     ├─ updateFenCache(fenInfo, isEngine=True)
  │     ├─ If endgame -> onMoveGo(iccs)
  │     └─ Else -> showBestHint()  # arrow on board
  └─ 'info_move' -> moveInfoSignal -> engineView.onEngineMoveInfo()
```

### Cloud Query Flow
```
CloudDB.startQuery(position)
  ├─ Check move_cache (skip if cached)
  └─ Create NetQuery -> HTTP GET chessdb.cn
        └─ onQueryFinished() -> parse pipe-delimited response
              ├─ Convert scores to Red's perspective
              ├─ Compute diff from best
              ├─ updateCache() -> Globl.fenCache
              └─ query_result_signal.emit()
                    └─ MainWindow.onCloudQueryResult()
                          ├─ updateFenCache(query)
                          ├─ Merge with boardActions
                          └─ actionsView.updateActions()
```

---

## Engine Integration

**EngineManager** (`Engine.py`):
- Wraps `cchess.UciEngine` or `cchess.UcciEngine`
- Runs in background thread via `ThreadRunner`
- Polls `engine.get_action()` in loop
- Signals: `readySignal`, `moveBestSignal`, `moveInfoSignal`, `checkmateSignal`, `drawSignal`

**EngineWidget** (`Widgets.py`):
- Three modes: `deep` (precise), `quick` (fast), `fight` (challenge)
- UI: mode radio buttons, MultiPV spin, red/black/analysis checkboxes
- Tree view for MultiPV analysis lines
- Params dict manages all engine settings (depth, movetime, threads, hash, etc.)

---

## Database Layer

### Local SQLite (Peewee ORM)
| Class | File | Purpose |
|-------|------|---------|
| `MasterBook` | `Game/masterbook.db` | Master opening book (EvPosition table) |
| `LocalBook` | `Game/localbook.db` | User's saved games (Book, Bookmark tables) |
| `OpenBookYfk` | User-selected `.yfk` | Yongfang format opening book |
| `OpenBookPF` | User-selected `.pfbook` | Pengfei format opening book |

**Lookup strategy:** All use `zhash` (Zobrist hash), check both normal and mirrored positions.

### Cloud DB
- Service: `http://www.chessdb.cn/chessdb.php`
- Async HTTP via `QNetworkAccessManager`
- Response: pipe-delimited move list with scores

### Endgame Storage
- TinyDB (`Game/endbooks.json`) via `EndBookStore`

---

## Settings Management

### Two-tier system:

1. **QSettings** (`Globl.settings`) - Qt registry/INI for UI state:
   - `geometry`, `windowState` - window position/size
   - `soundVolume`, `cloudMode` - preferences
   - `boardSkin`, `lastOpenFolder` - UI preferences
   - `history/h_splitter/sizes`, `history/v_splitter/sizes` - splitter positions
   - Engine params stored under their key names
   - `showScore` - score display toggle (in HistoryWidget.saveSettings/loadSettings)

2. **ConfigParser** (`XQMagic.ini`) - App configuration:
   - `[MainEngine]` section: `engine_type`, `engine_exec`

**Flow:** `readSettings()` in `__init__`, `saveSettings()` in `closeEvent()`. Each widget has `loadSettings()`/`saveSettings()` methods.

---

## Key Conventions

- **Scores:** Always from Red's perspective. When Black moves, scores are negated.
- **Mirror handling:** All DB lookups check both position and its mirror (left-right flipped).
- **Signal/Slot:** Extensive PyQt5 signals for decoupled communication.
- **Global state:** `Globl.py` module holds shared state (fenCache, singletons, widget refs).
- **ICCS notation:** Standard ICCS move format (e.g., "h2e2" for piece from h2 to e2).

---

## Important Methods in MainWindow

| Method | Purpose |
|--------|---------|
| `onMoveGo(iccs)` | Execute a move, update all views |
| `onChangePosition(isForward)` | Handle position change, query cloud/engine |
| `onTryBoardMove(from, to)` | Validate and execute board move |
| `onTryBookMove(act)` | Execute a book move from actionsView |
| `onTryEngineMove(action)` | Handle engine's best move |
| `onEngineMoveInfo(info)` | Update engine analysis display |
| `localSearch()` | Query all opening books for current position |
| `updateFenCache(fenInfo, isEngine)` | Update position cache with scores |
| `onCloudQueryResult(query)` | Process cloud DB query results |
| `runEngine(position)` | Start engine analysis for position |
| `onReviewByCloud()` / `onReviewByEngine()` | Start game review |
| `setGameMode(mode)` | Switch game mode |
| `initGame(fen)` | Initialize a new game from FEN |

---

## HistoryWidget Key Methods

| Method | Purpose |
|--------|---------|
| `onNewPostion(position, show)` | Add new position to move list |
| `onUpdatePosition(position)` | Update a position's display (scores, marks) |
| `setShowScore(yes)` | Toggle score display, refreshes all rows |
| `setSimpleMode(yes)` | Hide/show annotation/branch panels |
| `selectRow(row)` | Programmatically select a move row |
| `clear()` | Clear all moves |
| `getCurrPosition()` | Get current position dict |
| `loadSettings()` / `saveSettings()` | Persist splitter positions and showScore state |

---

## BoardActionsWidget Key Methods

| Method | Purpose |
|--------|---------|
| `updateActions(actions)` | Display move candidates with scores |
| `clear()` | Clear the move list |
| `onSelectIndex(index)` | Emit selected move signal |

---

## Common Patterns

### Adding a new dock widget
1. Create class inheriting `QDockWidget` in `Widgets.py`
2. Instantiate in `MainWindow.__init__`
3. Call `self.addDockWidget(area, widget)`
4. Add toggle action in window menu
5. Add `loadSettings()`/`saveSettings()` methods

### Adding a new checkbox/toggle to a widget
1. Create `QCheckBox` in widget's `__init__`
2. Add to layout
3. Connect signal in `MainWindow.__init__` after widget creation
4. Add to `loadSettings()`/`saveSettings()` for persistence

### Updating display when state changes
- If a toggle affects existing rows/items, iterate and re-render (see `setShowScore`)
- Don't just update the flag - call the render method for each existing item
