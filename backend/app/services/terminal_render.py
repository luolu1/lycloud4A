"""终端输出渲染器：把带控制序列的原始会话流还原成可读文本。

客户端通过 ``ssh ... | tee``（MobaXterm）或 SecureCRT/NatCatty 的会话日志
拿到的是**原始伪终端字节流**，里面包含光标移动、擦除、清屏、退格、回车覆盖、
OSC 标题、字符集切换等控制序列。直接用正则删除 ``\\x1b[...`` 只能去掉一部分，
剩下的 ``\\r``/``\\x08``/``\\x07`` 以及整屏编辑器（vim/less/htop）的重绘内容
依然会以乱码形式留在日志里。

本模块用一个很小的虚拟屏幕来重放这些控制序列，只保留操作者实际看到的内容：

* CSI（``ESC [ ... final``）实现光标移动 / 擦除 / 清屏，忽略 SGR 颜色；
* ``ESC ]``（OSC）、字符集切换（``ESC ( B``）、``ESC =``/``ESC >`` 等直接丢弃；
* ``\\r`` 回到行首、``\\x08`` 退格、``\\t`` 展开为空格，其余 C0/C1 控制符丢弃；
* 进入备用屏幕（DECSET 47/1047/1049，vim/less 等全屏程序）期间不绘制任何内容，
  这样日志保留的是 shell 操作轨迹，而不是 ``~`` 行和状态栏重绘噪声；
* 清屏（``ESC[H ESC[2J``）视为另起一屏，保留历史输出。

渲染是幂等的：对已经渲染过的文本再渲染一次结果不变，因此可以安全地同时用于
写入与读取两条路径。
"""

from __future__ import annotations

CSI_FINAL = {chr(code) for code in range(0x40, 0x7F)}
_ESCAPE_CHARSET_INTRO = set("()#%*+-./")


def _is_control(ch: str) -> bool:
    code = ord(ch)
    return code <= 0x1F or 0x7F <= code <= 0x9F


class TerminalRenderer:
    """把终端控制流增量重放为纯文本行。"""

    def __init__(self) -> None:
        self.lines: list[list[str]] = [[]]
        self.row = 0
        self.col = 0
        self.base = 0
        self.alt = False
        self.state = "normal"
        self.buf = ""

    # -- 输入 -------------------------------------------------------------
    def feed(self, data: str) -> None:
        for ch in data:
            self._consume(ch)

    # -- 内部工具 ---------------------------------------------------------
    def _ensure_line(self) -> None:
        while self.row >= len(self.lines):
            self.lines.append([])

    def _write(self, text: str) -> None:
        self._ensure_line()
        line = self.lines[self.row]
        if self.col > len(line):
            line.extend(" " * (self.col - len(line)))
        for ch in text:
            if self.col < len(line):
                line[self.col] = ch
            else:
                line.append(ch)
            self.col += 1

    # -- 状态机 -----------------------------------------------------------
    def _consume(self, ch: str) -> None:
        state = self.state
        if state == "esc":
            self._consume_esc(ch)
            return
        if state == "esc_charset":
            self.state = "normal"
            return
        if state == "csi":
            self.buf += ch
            if ch in CSI_FINAL:
                self._csi(self.buf)
                self.state = "normal"
                self.buf = ""
            return
        if state == "osc":
            if ch == "\x07":
                self.state = "normal"
                self.buf = ""
            elif ch == "\x1b":
                self.state = "osc_esc"
            return
        if state == "osc_esc":
            self.state = "normal" if ch == "\\" else "osc"
            return

        if ch == "\x1b":
            self.state = "esc"
            self.buf = ""
        elif ch == "\x9b":  # 8 位 CSI
            self.state = "csi"
            self.buf = ""
        elif ch == "\x08":  # 退格
            if not self.alt:
                self.col = max(0, self.col - 1)
        elif ch == "\r":
            if not self.alt:
                self.col = 0
        elif ch == "\n":
            if not self.alt:
                self.row += 1
                self.col = 0
                self._ensure_line()
        elif ch == "\t":
            if not self.alt:
                self._write(" " * (8 - (self.col % 8)))
        elif not self.alt and not _is_control(ch):
            self._write(ch)

    def _consume_esc(self, ch: str) -> None:
        if ch == "[":
            self.state = "csi"
            self.buf = ""
            return
        if ch == "]":
            self.state = "osc"
            self.buf = ""
            return
        if ch in _ESCAPE_CHARSET_INTRO:
            # 形如 ESC ( B 的字符集指定还需要再吞掉一个字节。
            self.state = "esc_charset"
            return
        # 其余单字符转义（ESC =、ESC >、ESC 7 ...）直接丢弃。
        self.state = "normal"
        self.buf = ""

    def _csi(self, seq: str) -> None:
        final = seq[-1]
        params = seq[:-1]
        is_private = "?" in params
        vals: list[int | None] = []
        for part in (
            params.replace("?", "")
            .replace(">", "")
            .replace("<", "")
            .replace("=", "")
            .split(";")
        ):
            if part == "":
                vals.append(None)
            else:
                try:
                    vals.append(int(part, 10))
                except ValueError:
                    vals.append(None)

        n = vals[0] if vals and vals[0] else 1

        if final in ("h", "l") and is_private:
            if any(v in (47, 1047, 1049) for v in vals if v is not None):
                self.alt = final == "h"
                return

        if self.alt:
            return

        if final == "A":
            self.row = max(self.base, self.row - n)
            self._ensure_line()
        elif final in ("B", "E"):
            self.row += n
            if final == "E":
                self.col = 0
            self._ensure_line()
        elif final == "C":
            self.col += n
        elif final == "D":
            self.col = max(0, self.col - n)
        elif final == "F":
            self.row = max(self.base, self.row - n)
            self.col = 0
            self._ensure_line()
        elif final == "G":
            self.col = max(0, n - 1)
        elif final in ("H", "f"):
            row_n = vals[0] if len(vals) > 0 else None
            col_n = vals[1] if len(vals) > 1 else None
            self.row = self.base + max(0, (row_n or 1) - 1)
            self.col = max(0, (col_n or 1) - 1)
            self._ensure_line()
        elif final == "J":
            self._erase_display((vals[0] or 0) if vals else 0)
        elif final == "K":
            self._erase_line((vals[0] or 0) if vals else 0)
        # "m"（颜色/样式）及其它序列对纯文本没有意义，直接忽略。

    def _erase_line(self, mode: int) -> None:
        self._ensure_line()
        line = self.lines[self.row]
        if mode == 1:
            for i in range(0, min(self.col, len(line) - 1) + 1):
                line[i] = " "
        elif mode == 2:
            self.lines[self.row] = []
        else:
            del line[self.col:]

    def _erase_display(self, mode: int) -> None:
        self._ensure_line()
        if mode == 2:
            # clear（ESC[H ESC[2J）另起一屏，保留操作者已看到的历史输出。
            if any(self.lines[self.base:]):
                self.lines.append([])
                self.base = len(self.lines) - 1
            self.row = self.base
            self.col = 0
        elif mode == 1:
            for i in range(self.base, self.row):
                self.lines[i] = []
            self._erase_line(1)
        elif mode == 0:
            self._erase_line(0)
            del self.lines[self.row + 1:]

    # -- 输出 -------------------------------------------------------------
    def to_string(self) -> str:
        out = "\n".join("".join(line).rstrip(" \t") for line in self.lines)
        return out.rstrip("\n")


def render_terminal(text: str) -> str:
    """把一段原始终端会话流渲染成可读文本。"""

    renderer = TerminalRenderer()
    renderer.feed(text)
    return renderer.to_string()
