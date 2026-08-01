# -*- coding: utf-8 -*-
"""
Nicos Weg A1 生词提取工具
==========================
- 上/下方向键、Space / Enter 控制浏览
- 鼠标选中单词或词组，点击 [提取所选词] 或按 Ctrl+Enter
- 完成浏览后，点击 [保存生词到文件] 一键导出
"""

import os
import re
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime


APP_TITLE = "Nicos Weg A1 生词提取工具 + 学习模式"
DEFAULT_SOURCE_NAME = "nico weg A1.txt"
DEFAULT_LEARNING_NAME = "word A1 1-400.txt"


# ====== 配色 + 字体 (友好现代风,集中管理方便日后调整) ======
PALETTE = {
    "primary":       "#5b8def",  # 主色 — 柔蓝 (按钮 / 高亮)
    "primary_dark":  "#3d6fd0",  # 主色深 — 标题 / 头部
    "primary_hover": "#3d6fd0",  # 主色悬停态
    "primary_text":  "#ffffff",  # 主色按钮上的文字
    "accent":        "#ff9f43",  # 强调色 — 暖橙
    "accent_hover":  "#e8893d",
    "success":       "#26ae60",  # 成功色 — 薄荷绿 (保存按钮)
    "success_hover": "#1f9654",
    "danger":        "#e74c3c",
    "warning":       "#f39c12",
    "bg":            "#eef1f6",  # 整体背景 — 极淡蓝灰
    "surface":       "#ffffff",  # 卡片背景 — 白
    "surface_alt":   "#f4f7fb",  # 备用卡片背景
    "border":        "#d0d7e2",  # 软边框
    "text":          "#2c3e50",  # 主文字 — 深海军蓝
    "text_muted":    "#7f8c9b",  # 次要文字
    "highlight":     "#fff8c5",  # 软黄高亮
    "current":       "#ffd54f",  # 当前行高亮
    "context_bg":    "#fbfcfd",  # 上下文行背景
}

FONT_DEFAULT  = ("Segoe UI", 10)
FONT_SMALL    = ("Segoe UI", 9)
FONT_BOLD     = ("Segoe UI", 10, "bold")
FONT_HEADING  = ("Segoe UI", 11, "bold")
FONT_TITLE    = ("Segoe UI", 14, "bold")
FONT_MONO     = ("Consolas", 11)
FONT_MONO_BIG = ("Consolas", 13, "bold")


class WordExtractor:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1080x820")
        self.root.minsize(820, 640)
        self.root.configure(bg=PALETTE["bg"])

        # 初始化全局样式 (必须在构建任何控件之前调用)
        self._init_styles()

        # 路径与数据
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.default_source = os.path.join(self.script_dir, DEFAULT_SOURCE_NAME)
        self.source_path = self.default_source

        self.lines = []               # 原文所有行
        self.current_line = 0         # 当前光标行（从 0 起）
        self.words = []               # [(word, line_no), ...]
        self.persist_path = None      # 持久化文件路径 (__init__ 里赋值)
        self.context_size = 4         # 当前行上下各显示几行（默认 ±4,共 9 行）
        self.section_indices = []     # [(line_no, "A1-01"), ...] 集标题错点

        # 学习模式
        self.learning_items = []      # 解析后的学习点 list[dict]
        self.learning_path = None     # 学习数据文件路径 (只读,绝不会被程序写入)
        self.learning_index = None    # 当前学习点在 self.learning_items 中的下标
        self._learn_line_to_text = {} # 原文行号 -> learn_text 的 Tk 行号 (用于滚动)
        self.notebook = None
        self.learn_status_var = None
        self.learn_seq_entry = None
        self.learn_file_var = None    # 显示当前单词本文件名的 Label
        self.learn_count_var = None   # 显示学习点数量的 Label
        self.learn_text = None        # 原文区 (整个文章,学习点位置高亮,只读)
        self.learn_explain = None     # 当前学习点的解释区 (只读)

        # 控件引用
        self.file_label = None
        self.line_label = None
        self.text_widget = None
        self.listbox = None
        self.jump_entry = None
        self.word_count_label = None
        self.status_bar = None
        self.dedupe_var = None
        self.autonext_var = None

        # 构建 UI
        self._create_ui()
        # 尝试加载默认文件
        if not self._try_load_default():
            # 让用户选一个文件
            self._choose_file()
        else:
            self._show_current_line()
        # 加载默认学习文件
        self._try_load_default_learning()
        # 初始化持久化文件路径 (必须在 source_path 确定之后) 并加载上次的提取
        self.persist_path = os.path.join(self.script_dir, "extracted_words.json")
        self._load_persisted_words()

    # -------------------------------------------------------------- 加载文件
    def _try_load_default(self) -> bool:
        if os.path.exists(self.default_source):
            return self._load_file(self.default_source)
        return False

    def _load_file(self, path: str) -> bool:
        try:
            # 切换文件: 先把当前提取持久化 (防止丢失), 再清空 UI
            if getattr(self, "persist_path", None) and self.words:
                self._persist_words()
            with open(path, "r", encoding="utf-8") as f:
                self.lines = f.readlines()
            self.source_path = path
            self.current_line = 0
            self.words.clear()
            self.listbox.delete(0, tk.END)
            self._update_word_count()
            if self.file_label is not None:
                self.file_label.config(text=os.path.basename(path))
            self._build_section_index()
            return True
        except Exception as e:
            messagebox.showerror("加载失败", str(e))
            return False

    def _choose_file(self):
        path = filedialog.askopenfilename(
            title="选择脚本文件",
            initialdir=self.script_dir,
            filetypes=[("Text", "*.txt"), ("All", "*.*")],
        )
        if not path:
            if not self.lines:
                # 用户取消且无内容 -> 退出
                self.root.destroy()
            return
        if self._load_file(path):
            self._show_current_line()
            # 切换文件后恢复新文件的已保存单词
            self._load_persisted_words()
            # 学习模式同步切换: 重新解析当前单词本(行号可能需要对应新原文)
            if self.learning_items:
                self._reload_learning_file()

    # -------------------------------------------------------------- 样式定义
    def _init_styles(self):
        """集中配置 ttk 控件样式 + 全局默认字体,使界面协调统一。"""
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")  # clam 主题允许更多自定义
        except tk.TclError:
            pass

        # 全局默认字体
        style.configure(".", font=FONT_DEFAULT, background=PALETTE["bg"])
        style.configure("TFrame", background=PALETTE["bg"])
        style.configure("Surface.TFrame", background=PALETTE["surface"])

        # LabelFrame (卡片) — 圆角感外观
        style.configure(
            "Card.TLabelframe",
            background=PALETTE["surface"],
            bordercolor=PALETTE["border"],
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=PALETTE["surface"],
            foreground=PALETTE["primary_dark"],
            font=FONT_HEADING,
            padding=(10, 4),
        )

        # Label — 普通/次要/标题
        style.configure("TLabel", background=PALETTE["bg"], foreground=PALETTE["text"])
        style.configure(
            "Surface.TLabel",
            background=PALETTE["surface"],
            foreground=PALETTE["text"],
        )
        style.configure("Muted.TLabel", background=PALETTE["surface"],
                         foreground=PALETTE["text_muted"], font=FONT_SMALL)
        style.configure("Title.TLabel",
                         background=PALETTE["surface"],
                         foreground=PALETTE["primary_dark"],
                         font=FONT_TITLE)
        style.configure("Primary.TLabel",
                         background=PALETTE["bg"],
                         foreground=PALETTE["primary_dark"],
                         font=FONT_HEADING)

        # 强调信息条 (顶部条/单词本信息条)
        style.configure("Info.TLabel",
                         background=PALETTE["surface"],
                         foreground=PALETTE["text"],
                         font=FONT_BOLD)

        # Button — 默认 / 主要动作
        style.configure(
            "TButton",
            font=FONT_DEFAULT,
            padding=(10, 5),
            background=PALETTE["surface_alt"],
            foreground=PALETTE["text"],
            bordercolor=PALETTE["border"],
            borderwidth=1,
            relief="raised",
        )
        style.map(
            "TButton",
            background=[("active", PALETTE["surface_alt"]), ("pressed", PALETTE["border"])],
            foreground=[("disabled", PALETTE["text_muted"])],
            relief=[("pressed", "sunken")],
        )

        # 主操作按钮 — 蓝 (用于「提取所选词」)
        style.configure(
            "Primary.TButton",
            font=FONT_BOLD,
            padding=(12, 5),
            background=PALETTE["primary"],
            foreground=PALETTE["primary_text"],
            bordercolor=PALETTE["primary_dark"],
            borderwidth=0,
        )
        style.map(
            "Primary.TButton",
            background=[("active", PALETTE["primary_hover"]), ("pressed", PALETTE["primary_dark"])],
            foreground=[("disabled", PALETTE["text_muted"])],
        )

        # 保存按钮 — 绿
        style.configure(
            "Success.TButton",
            font=FONT_BOLD,
            padding=(14, 6),
            background=PALETTE["success"],
            foreground=PALETTE["primary_text"],
            bordercolor=PALETTE["success_hover"],
            borderwidth=0,
        )
        style.map(
            "Success.TButton",
            background=[("active", PALETTE["success_hover"]), ("pressed", "#178047")],
            foreground=[("disabled", PALETTE["text_muted"])],
        )

        # 学习模式专用 — 橙
        style.configure(
            "Accent.TButton",
            font=FONT_BOLD,
            padding=(12, 5),
            background=PALETTE["accent"],
            foreground=PALETTE["primary_text"],
            bordercolor=PALETTE["accent_hover"],
            borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", PALETTE["accent_hover"]), ("pressed", "#c97a31")],
        )

        # Entry
        style.configure(
            "TEntry",
            fieldbackground=PALETTE["surface"],
            foreground=PALETTE["text"],
            bordercolor=PALETTE["border"],
            lightcolor=PALETTE["border"],
            darkcolor=PALETTE["border"],
            padding=4,
        )

        # Radiobutton
        style.configure(
            "TRadiobutton",
            background=PALETTE["surface"],
            foreground=PALETTE["text"],
            padding=(4, 2),
        )

        # Checkbutton
        style.configure(
            "TCheckbutton",
            background=PALETTE["surface"],
            foreground=PALETTE["text"],
            padding=(4, 2),
        )

        # Notebook (顶部分页)
        style.configure(
            "TNotebook",
            background=PALETTE["bg"],
            bordercolor=PALETTE["border"],
            borderwidth=0,
        )
        style.configure(
            "TNotebook.Tab",
            background=PALETTE["surface_alt"],
            foreground=PALETTE["text_muted"],
            padding=(18, 8),
            font=FONT_BOLD,
            bordercolor=PALETTE["border"],
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", PALETTE["primary"]), ("active", PALETTE["surface_alt"])],
            foreground=[("selected", PALETTE["primary_text"])],
            font=[("selected", FONT_BOLD)],
        )

        # Separator
        style.configure("TSeparator", background=PALETTE["border"])

        # PanedWindow Sash (学习模式分隔条)
        style.configure("Sash", background=PALETTE["border"], sashthickness=6)

        # Scrollbar
        style.configure(
            "Vertical.TScrollbar",
            background=PALETTE["surface_alt"],
            bordercolor=PALETTE["border"],
            arrowcolor=PALETTE["text_muted"],
            troughcolor=PALETTE["bg"],
        )
        style.configure(
            "Horizontal.TScrollbar",
            background=PALETTE["surface_alt"],
            bordercolor=PALETTE["border"],
            arrowcolor=PALETTE["text_muted"],
            troughcolor=PALETTE["bg"],
        )

        # Status bar
        style.configure("Status.TLabel",
                         background=PALETTE["primary_dark"],
                         foreground=PALETTE["primary_text"],
                         font=FONT_SMALL,
                         padding=(8, 4))

    # -------------------------------------------------------------- UI 构建
    def _create_ui(self):
        # ===== 顶部信息条 (header card) =====
        header = tk.Frame(
            self.root, bg=PALETTE["primary_dark"], height=56,
        )
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        # 左侧 logo + 标题
        tk.Label(
            header, text="🇩🇪  Nicos Weg A1 · 生词本",
            bg=PALETTE["primary_dark"], fg=PALETTE["primary_text"],
            font=FONT_TITLE,
        ).pack(side=tk.LEFT, padx=(16, 18))
        # 分隔
        tk.Frame(header, bg=PALETTE["primary"], width=2).pack(side=tk.LEFT, fill=tk.Y, pady=12)
        # 当前文件标签
        tk.Label(
            header, text="📄",
            bg=PALETTE["primary_dark"], fg=PALETTE["primary_text"],
            font=FONT_BOLD,
        ).pack(side=tk.LEFT, padx=(14, 4))
        self.file_label = tk.Label(
            header, text="(未加载)",
            bg=PALETTE["primary_dark"], fg="#cfe0ff",
            font=FONT_DEFAULT, anchor=tk.W,
        )
        self.file_label.pack(side=tk.LEFT, padx=(0, 12), fill=tk.X, expand=True)
        # 顶部右侧按钮 — 用 tk.Button 自定义色 (因为 clam 主题对 accent 背景支持有限)
        def _header_btn(parent, text, cmd, bg, hover):
            b = tk.Button(
                parent, text=text, command=cmd,
                font=FONT_BOLD, fg="white", bg=bg,
                activebackground=hover, activeforeground="white",
                relief=tk.FLAT, bd=0, padx=14, pady=6, cursor="hand2",
            )
            b.bind("<Enter>", lambda e, btn=b: btn.config(bg=hover))
            b.bind("<Leave>", lambda e, btn=b: btn.config(bg=bg))
            return b
        btn_choose = _header_btn(header, "📁 选择其他文件…", self._choose_file,
                                  PALETTE["primary"], PALETTE["primary_hover"])
        btn_choose.pack(side=tk.RIGHT, padx=4, pady=10)
        btn_find = _header_btn(header, "🔍 查找词", self._find_word,
                                PALETTE["primary"], PALETTE["primary_hover"])
        btn_find.pack(side=tk.RIGHT, padx=4, pady=10)

        # ===== Notebook:切换浏览/学习两种模式 =====
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 6))
        browse_page = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(browse_page, text="   📖  浏览 / 提取   ")
        study_page = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(study_page, text="   📚  学习模式   ")
        self._build_study_page(study_page)

        # ===== 当前行展示区 (卡片) =====
        cur = ttk.LabelFrame(
            browse_page,
            text="  📖  当前行  ·  用鼠标拖选要提取的单词或词组  ",
            padding=10, style="Card.TLabelframe",
        )
        cur.pack(fill=tk.X, padx=4, pady=(6, 6))

        self.line_label = ttk.Label(cur, text="", style="Surface.TLabel",
                                     foreground=PALETTE["text_muted"], font=FONT_SMALL)
        self.line_label.pack(anchor=tk.W, padx=2, pady=(0, 4))

        text_holder = tk.Frame(
            cur, bg=PALETTE["surface"],
            highlightthickness=1, highlightbackground=PALETTE["border"],
        )
        text_holder.pack(fill=tk.X, pady=2)
        self.text_widget = tk.Text(
            text_holder, height=12, font=FONT_MONO_BIG,
            wrap=tk.NONE, padx=10, pady=10, bd=0,
            bg=PALETTE["surface"], fg=PALETTE["text"],
            insertbackground=PALETTE["primary"],
            selectbackground=PALETTE["primary"],
            selectforeground=PALETTE["primary_text"],
            inactiveselectbackground=PALETTE["border"],
        )
        text_scroll = ttk.Scrollbar(text_holder, orient=tk.HORIZONTAL, command=self.text_widget.xview)
        text_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.text_widget.config(xscrollcommand=text_scroll.set)
        self.text_widget.pack(fill=tk.X)
        # tag 配置 (使用 PALETTE)
        self.text_widget.tag_configure(
            "current_line", background=PALETTE["current"],
            font=FONT_MONO_BIG,
        )
        self.text_widget.tag_configure(
            "context_line", background=PALETTE["context_bg"],
            font=FONT_MONO,
        )
        self.text_widget.tag_configure(
            "line_prefix", foreground=PALETTE["text_muted"],
            font=("Consolas", 11),
        )
        self.text_widget.config(state=tk.DISABLED, cursor="arrow")

        # ===== 行号导航按钮 (第一排) =====
        btn_row = ttk.Frame(cur, style="Surface.TFrame")
        btn_row.pack(fill=tk.X, pady=(8, 4))
        ttk.Button(btn_row, text="⇑  上一段", command=self._prev_line).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="⇓  下一段  (Space)", command=self._next_line).pack(side=tk.LEFT, padx=2)
        ttk.Separator(btn_row, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(btn_row, text="↑ -1", width=5, command=lambda: self._step_one(-1)).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_row, text="+1 ↓", width=5, command=lambda: self._step_one(1)).pack(side=tk.LEFT, padx=1)
        ttk.Separator(btn_row, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        # 主操作: 提取所选词 — Primary (蓝)
        ttk.Button(
            btn_row, text="✓  提取所选词  (Ctrl+Enter)",
            command=self._extract_selection, style="Primary.TButton",
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="提取整行", command=self._extract_whole_line).pack(side=tk.LEFT, padx=2)
        ttk.Separator(btn_row, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Label(btn_row, text="跳到行号:", style="Surface.TLabel").pack(side=tk.LEFT, padx=(2, 4))
        self.jump_entry = ttk.Entry(btn_row, width=7)
        self.jump_entry.pack(side=tk.LEFT)
        self.jump_entry.bind("<Return>", lambda e: self._goto_line())
        ttk.Button(btn_row, text="跳转 →", command=self._goto_line).pack(side=tk.LEFT, padx=2)

        # ===== 第二排按钮 =====
        btn_row2 = ttk.Frame(cur, style="Surface.TFrame")
        btn_row2.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(btn_row2, text="上下文:", style="Surface.TLabel").pack(side=tk.LEFT, padx=(2, 4))
        self.context_size_var = tk.IntVar(value=self.context_size)
        for n in (2, 4, 6, 10, 20):
            ttk.Radiobutton(
                btn_row2, text=f"±{n}", value=n,
                variable=self.context_size_var, width=5,
                command=lambda x=n: self._set_context_size(x),
                style="TRadiobutton",
            ).pack(side=tk.LEFT, padx=1)
        ttk.Separator(btn_row2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(btn_row2, text="⤒  顶部", command=self._goto_start).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row2, text="⤓  底部", command=self._goto_end).pack(side=tk.LEFT, padx=2)
        ttk.Separator(btn_row2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(btn_row2, text="⬆  上一集", command=lambda: self._jump_to_section(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row2, text="下一集  ⬇", command=lambda: self._jump_to_section(1)).pack(side=tk.LEFT, padx=2)

        # ===== 已提取区 (卡片) =====
        lst = ttk.LabelFrame(
            browse_page,
            text="  ✏️  已提取的生词 / 词组  ·  双击可删除  ",
            padding=10, style="Card.TLabelframe",
        )
        lst.pack(fill=tk.BOTH, expand=True, padx=4, pady=(6, 6))

        opt_row = ttk.Frame(lst, style="Surface.TFrame")
        opt_row.pack(fill=tk.X)
        self.dedupe_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt_row, text="自动去重 (已存在的词不再加入)",
            variable=self.dedupe_var, style="TCheckbutton",
        ).pack(side=tk.LEFT)
        self.autonext_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opt_row, text="提取后自动下一行",
            variable=self.autonext_var, style="TCheckbutton",
        ).pack(side=tk.LEFT, padx=20)

        list_frame = tk.Frame(
            lst, bg=PALETTE["surface_alt"],
            highlightthickness=1, highlightbackground=PALETTE["border"],
        )
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 6))
        self.listbox = tk.Listbox(
            list_frame,
            font=("Segoe UI", 11), selectmode=tk.SINGLE,
            bg=PALETTE["surface"], fg=PALETTE["text"],
            selectbackground=PALETTE["primary"],
            selectforeground=PALETTE["primary_text"],
            highlightthickness=0, bd=0, relief=tk.FLAT,
            activestyle="none", height=8,
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        self.listbox.bind("<Double-Button-1>", lambda e: self._delete_selected())

        list_btn_row = ttk.Frame(lst, style="Surface.TFrame")
        list_btn_row.pack(fill=tk.X)
        ttk.Button(list_btn_row, text="🗑  删除所选  (Del)", command=self._delete_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(list_btn_row, text="↑  上移", command=lambda: self._move_item(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(list_btn_row, text="↓  下移", command=lambda: self._move_item(1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(list_btn_row, text="清空全部", command=self._clear_all).pack(side=tk.LEFT, padx=12)
        # 保存按钮: 放在最右边, 醒目绿底 (Success 样式)
        self.save_btn = ttk.Button(
            list_btn_row, text="💾  保存生词到文件",
            command=self._save_words, style="Success.TButton",
        )
        self.save_btn.pack(side=tk.RIGHT, padx=(8, 2))

        # ===== 底部: 状态条 (只保留统计) =====
        bottom = ttk.Frame(browse_page, style="TFrame", padding=(4, 6))
        bottom.pack(fill=tk.X, padx=4, pady=(0, 4))
        # 左侧: 数量统计 — 用 accent 色突出
        self.word_count_label = tk.Label(
            bottom,
            text="📊 已提取: 0 个",
            bg=PALETTE["bg"], fg=PALETTE["primary_dark"],
            font=FONT_HEADING, anchor=tk.W, padx=6,
        )
        self.word_count_label.pack(side=tk.LEFT)
        ttk.Button(bottom, text="📋  复制全部到剪贴板",
                    command=self._copy_to_clipboard).pack(side=tk.RIGHT, padx=4)

        # ===== 状态栏 (底部深蓝条) =====
        status_frame = tk.Frame(self.root, bg=PALETTE["primary_dark"], height=28)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        self.status_bar = tk.Label(
            status_frame, text="✓ 就绪",
            bg=PALETTE["primary_dark"], fg=PALETTE["primary_text"],
            font=FONT_SMALL, anchor=tk.W, padx=14,
        )
        self.status_bar.pack(side=tk.LEFT, fill=tk.Y)

        # 快捷键
        self.root.bind("<Right>", lambda e: self._next_line())
        self.root.bind("<space>", lambda e: self._next_line())
        self.root.bind("<Next>", lambda e: self._next_line())
        self.root.bind("<Left>", lambda e: self._prev_line())
        self.root.bind("<Prior>", lambda e: self._prev_line())
        # Shift+方向键 = 单行精调
        self.root.bind("<Shift-Right>", lambda e: self._step_one(1))
        self.root.bind("<Shift-Left>", lambda e: self._step_one(-1))
        self.root.bind("<Shift-Up>", lambda e: self._step_one(-1))
        self.root.bind("<Shift-Down>", lambda e: self._step_one(1))
        # 单独的上下方向键、PageUp/PageDown 仍走 "大步" (与上下文联动)
        self.root.bind("<Down>", lambda e: self._next_line())
        self.root.bind("<Up>", lambda e: self._prev_line())
        self.root.bind("<Control-Return>", lambda e: self._extract_selection())
        self.root.bind("<Control-KP_Enter>", lambda e: self._extract_selection())
        self.root.bind("<Delete>", lambda e: self._delete_selected())

    # -------------------------------------------------------------- 学习模式 UI
    def _build_study_page(self, parent):
        """构建学习模式面板。
        设计: 上方 = 整篇原文(只读,学习点位置高亮,当前学习点橙色加粗);
              下方 = 当前学习点的解释。
        设计初衷跟浏览/提取页面保持一致:用户首先看到的是"整篇文章",只是多了高亮提醒。
        """
        # === 顶部控制栏 (card-style) ===
        top = ttk.Frame(parent, style="Surface.TFrame", padding=8)
        top.pack(fill=tk.X, padx=8, pady=(10, 6))

        ttk.Label(top, text="📍 状态:", style="Surface.TLabel",
                  font=FONT_BOLD).pack(side=tk.LEFT, padx=(2, 4))
        self.learn_status_var = tk.StringVar(value="(未加载)")
        ttk.Label(
            top, textvariable=self.learn_status_var,
            style="Primary.TLabel", font=("Segoe UI", 11, "bold"),
        ).pack(side=tk.LEFT, padx=2)

        ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=12)

        # 主操作: 上一个/下一个 — Accent (橙)
        ttk.Button(top, text="⬆  上一个", command=self._prev_learning,
                    style="Accent.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="下一个  ⬇", command=self._next_learning,
                    style="Accent.TButton").pack(side=tk.LEFT, padx=2)

        ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=12)

        ttk.Label(top, text="按序号跳转:", style="Surface.TLabel").pack(side=tk.LEFT, padx=(2, 4))
        self.learn_seq_entry = ttk.Entry(top, width=7)
        self.learn_seq_entry.pack(side=tk.LEFT)
        self.learn_seq_entry.bind("<Return>", lambda e: self._goto_learning_seq())
        ttk.Button(top, text="跳转 →", command=self._goto_learning_seq).pack(side=tk.LEFT, padx=2)

        ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=12)

        ttk.Button(top, text="🔄  重新加载", command=self._reload_learning_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="📖  选单词本…", command=self._choose_learning_file).pack(side=tk.LEFT, padx=2)
        ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=12)
        ttk.Button(top, text="📄  选原文…", command=self._choose_source_for_learning).pack(side=tk.LEFT, padx=2)

        # === 单词本信息条 (卡条) ===
        info = tk.Frame(
            parent, bg=PALETTE["surface_alt"],
            highlightthickness=1, highlightbackground=PALETTE["border"],
        )
        info.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.learn_file_var = tk.StringVar(value="📚 当前单词本: (未加载)")
        tk.Label(info, textvariable=self.learn_file_var,
                  bg=PALETTE["surface_alt"], fg=PALETTE["text"],
                  font=FONT_BOLD).pack(side=tk.LEFT, padx=10, pady=6)
        tk.Label(info, text="🔒 只读模式 (程序不会修改原文件)",
                  bg=PALETTE["surface_alt"], fg=PALETTE["warning"],
                  font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=4, pady=6)
        self.learn_count_var = tk.StringVar(value="")
        tk.Label(info, textvariable=self.learn_count_var,
                  bg=PALETTE["surface_alt"], fg=PALETTE["text_muted"],
                  font=FONT_SMALL).pack(side=tk.RIGHT, padx=10, pady=6)

        # === 左右排布: 原文 + 解释 (tk.PanedWindow 可拖动分隔条) ===
        self.learn_paned = tk.PanedWindow(
            parent, orient=tk.HORIZONTAL,
            sashrelief=tk.RAISED, sashwidth=6, sashpad=0,
            bg=PALETTE["border"], bd=0, relief=tk.FLAT,
            showhandle=False,
        )
        self.learn_paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # --- 左: 原文 ---
        src_holder = ttk.LabelFrame(
            self.learn_paned,
            text="  📄  原文  ·  • 学习点已高亮  ·  ▶ 为当前学习点  ",
            padding=6, style="Card.TLabelframe",
        )
        self.learn_paned.add(src_holder, minsize=320, stretch="always")

        src_frame = tk.Frame(
            src_holder, bg=PALETTE["surface"],
            highlightthickness=1, highlightbackground=PALETTE["border"],
        )
        src_frame.pack(fill=tk.BOTH, expand=True)

        self.learn_text = tk.Text(
            src_frame, font=("Consolas", 11), wrap=tk.NONE,
            padx=8, pady=8, bd=0,
            bg=PALETTE["surface"], fg=PALETTE["text"],
            selectbackground=PALETTE["primary"],
            selectforeground=PALETTE["primary_text"],
            inactiveselectbackground=PALETTE["border"],
        )
        src_scroll = ttk.Scrollbar(src_frame, orient=tk.VERTICAL, command=self.learn_text.yview)
        src_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.learn_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.learn_text.config(yscrollcommand=src_scroll.set, state=tk.DISABLED, cursor="arrow")
        # tag 配置 (使用 PALETTE)
        self.learn_text.tag_configure(
            "line_no", foreground=PALETTE["text_muted"], font=("Consolas", 10),
        )
        self.learn_text.tag_configure(
            "learn_marker", foreground=PALETTE["accent"],
            font=("Consolas", 11, "bold"),
        )
        self.learn_text.tag_configure("learn_point", background=PALETTE["highlight"])
        self.learn_text.tag_configure(
            "current_point", background=PALETTE["accent"],
            foreground=PALETTE["primary_text"],
            font=("Consolas", 11, "bold"),
        )
        self.learn_text.tag_configure(
            "current_marker", background=PALETTE["accent"],
            foreground=PALETTE["primary_text"],
            font=("Consolas", 11, "bold"),
        )

        # --- 右: 解释 ---
        exp_holder = ttk.LabelFrame(
            self.learn_paned,
            text="  📝  当前学习点解释  ",
            padding=6, style="Card.TLabelframe",
        )
        self.learn_paned.add(exp_holder, minsize=260, stretch="always")

        # 顶部:小按钮 [⤒ 跳到浏览页] — 在学习模式下手动查看完整上下文
        exp_top = ttk.Frame(exp_holder, style="Surface.TFrame")
        exp_top.pack(fill=tk.X)
        ttk.Button(exp_top, text="⤒  跳到浏览页查看上下文",
                    command=self._jump_source_line).pack(side=tk.RIGHT, padx=2, pady=(0, 4))

        exp_frame = tk.Frame(
            exp_holder, bg=PALETTE["surface_alt"],
            highlightthickness=1, highlightbackground=PALETTE["border"],
        )
        exp_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

        self.learn_explain = tk.Text(
            exp_frame, font=("Microsoft YaHei", 10), wrap=tk.WORD,
            padx=10, pady=10, bd=0,
            bg=PALETTE["surface_alt"], fg=PALETTE["text"],
            selectbackground=PALETTE["primary"],
            selectforeground=PALETTE["primary_text"],
            inactiveselectbackground=PALETTE["border"],
        )
        exp_scroll = ttk.Scrollbar(exp_frame, orient=tk.VERTICAL, command=self.learn_explain.yview)
        exp_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.learn_explain.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.learn_explain.config(yscrollcommand=exp_scroll.set, state=tk.DISABLED)
        # tag (使用 PALETTE)
        self.learn_explain.tag_configure(
            "seq_tag", foreground=PALETTE["accent"],
            font=("Consolas", 11, "bold"),
        )
        self.learn_explain.tag_configure(
            "target", foreground=PALETTE["text"], font=("Consolas", 12, "bold"),
            background=PALETTE["highlight"],
        )
        self.learn_explain.tag_configure(
            "heading", foreground=PALETTE["primary_dark"],
            font=("Microsoft YaHei", 12, "bold"),
        )
        self.learn_explain.tag_configure(
            "subheading", foreground=PALETTE["warning"],
            font=("Microsoft YaHei", 10, "bold"),
        )
        self.learn_explain.tag_configure("numbered", foreground=PALETTE["primary"])
        self.learn_explain.tag_configure("empty", foreground=PALETTE["text_muted"])

        # 默认分割位置: 左 65%, 右 35% (窗口首次 layout 后调用)
        self.root.after(80, self._place_learn_paned)

    # -------------------------------------------------------------- 学习数据加载
    def _place_learn_paned(self):
        """默认将学习页的左右分割位置设为 65%。可在调用本方法后多次重设 (例如窗口 resize 后)。"""
        try:
            total_w = self.learn_paned.winfo_width()
            if total_w > 1:
                x = int(total_w * 0.65)
                self.learn_paned.sash_place(0, x, 0)
        except Exception:
            pass

    def _try_load_default_learning(self):
        """加载默认学习文件"""
        default = os.path.join(self.script_dir, DEFAULT_LEARNING_NAME)
        if os.path.exists(default):
            return self._load_learning_file(default)
        if self.learn_status_var is not None:
            self._set_learning_status(f"未找到默认学习文件 {DEFAULT_LEARNING_NAME}")
        return False

    def _load_learning_file(self, path) -> bool:
        """加载学习文件 (只读,绝不会写入 path)。
        读取后按行号排序,这样“下一个/上一个”跟文章顺序一致。
        """
        items = self._parse_learning_file(path)
        # 按行号排序: 有行号的排前面并按行号升序,无行号的排最后并按序号
        items.sort(key=lambda x: (x["line"] is None, x["line"] or 0, x["seq"]))
        self.learning_items = items
        self.learning_path = path
        self.learning_index = None

        n_total = len(items)
        n_with_line = sum(1 for it in items if it["line"] is not None)

        # 顶部单词本信息条
        if self.learn_file_var is not None:
            self.learn_file_var.set(f"📚 当前单词本: {os.path.basename(path)}")
        if self.learn_count_var is not None:
            if n_total:
                self.learn_count_var.set(f"共 {n_total} 个学习点  •  带行号 {n_with_line} 个")
            else:
                self.learn_count_var.set("未解析出任何学习点")

        if n_total:
            self._set_learning_status(
                f"已加载 {n_total} 个学习点 ({n_with_line} 个带行号)。点击“下一个”开始学习。"
            )
        else:
            self._set_learning_status(f"该文件未解析出任何学习点")

        # 重渲染原文区 (还没有选中任何学习点,所以不高亮)
        self._render_source_text()
        self._render_explanation()
        return bool(n_total)

    def _parse_learning_file(self, path):
        """解析学习数据文件。格式: ## N\\n行号: M\\ntarget\\n### 子章节\\n..."""
        items = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
            lines = raw.splitlines(keepends=False)
        except Exception as e:
            messagebox.showerror("加载失败", f"无法读取 {path}:\n{e}")
            return items

        n = len(lines)
        i = 0
        pat_seq = re.compile(r"^##\s*(\d+)\s*$")
        # “行号:21 / 行号：21 / 行号 21 / 行号: 21”都接受
        pat_line = re.compile(r"^行号[^\d\-]*?(\d+)\s*$")

        while i < n:
            m = pat_seq.match(lines[i].strip())
            if not m:
                i += 1
                continue
            seq = int(m.group(1))
            item = {"seq": seq, "line": None, "target": "", "sections": []}
            i += 1

            # 读 "行号"
            if i < n:
                m2 = pat_line.match(lines[i].strip())
                if m2:
                    item["line"] = int(m2.group(1))
                    i += 1

            # 读 target / sections
            target_lines = []
            cur_section = None
            while i < n:
                line = lines[i].rstrip("\n").rstrip("\r")
                if pat_seq.match(line.strip()):
                    break
                if line.lstrip().startswith("###"):
                    title = line.lstrip("#").strip()
                    cur_section = [title, []]
                    item["sections"].append(cur_section)
                    i += 1
                    continue
                if cur_section is None:
                    if line.strip():
                        target_lines.append(line.strip())
                else:
                    cur_section[1].append(line)
                i += 1

            item["target"] = " ".join(target_lines).strip()
            item["sections"] = [(t, "\n".join(b).rstrip()) for t, b in item["sections"]]
            items.append(item)

        return items

    def _reload_learning_file(self):
        if self.learning_path and os.path.exists(self.learning_path):
            self._load_learning_file(self.learning_path)
            self._set_status(f"已重新加载 {os.path.basename(self.learning_path)}")
        else:
            self._try_load_default_learning()

    def _choose_learning_file(self):
        path = filedialog.askopenfilename(
            title="选择学习数据文件",
            initialdir=self.script_dir,
            filetypes=[("Text", "*.txt"), ("All", "*.*")],
        )
        if path:
            self._load_learning_file(path)

    def _choose_source_for_learning(self):
        """在"学习模式"里单独切换原文文件,同时更新学习点的行号映射。"""
        path = filedialog.askopenfilename(
            title="选择原文文件",
            initialdir=self.script_dir,
            filetypes=[("Text", "*.txt"), ("All", "*.*")],
        )
        if not path:
            return
        if self._load_file(path):
            self._show_current_line()
            self._load_persisted_words()
            # 重新渲染学习页的原文区 (行号映射已更新)
            if self.learning_items:
                self._reload_learning_file()

    def _set_learning_status(self, msg):
        if self.learn_status_var is not None:
            self.learn_status_var.set(msg)

    # -------------------------------------------------------------- 学习导航
    def _prev_learning(self):
        if not self.learning_items:
            return
        if self.learning_index is None:
            idx = 0
        else:
            idx = max(0, self.learning_index - 1)
        self.learning_index = idx
        self._apply_learning_index()

    def _next_learning(self):
        if not self.learning_items:
            return
        if self.learning_index is None:
            idx = 0
        else:
            idx = min(len(self.learning_items) - 1, self.learning_index + 1)
        self.learning_index = idx
        self._apply_learning_index()

    def _goto_learning_seq(self):
        if not self.learning_items:
            return
        try:
            seq = int(self.learn_seq_entry.get().strip())
        except ValueError:
            messagebox.showinfo("提示", "请输入有效的序号(整数)")
            return
        for i, it in enumerate(self.learning_items):
            if it["seq"] == seq:
                self.learning_index = i
                self._apply_learning_index()
                return
        self._set_learning_status(f"未找到序号 ## {seq}")

    def _apply_learning_index(self):
        """切换学习点:重渲染原文 (高亮当前位置) + 解释 + 同步浏览模式。"""
        # 重渲染原文 (包含新当前学习点高亮)
        self._render_source_text()
        # 重渲染解释区
        self._render_explanation()
        # 状态栏
        if self.learning_index is None or not self.learning_items:
            return
        item = self.learning_items[self.learning_index]
        n_total = len(self.learning_items)
        pos = self.learning_index + 1
        ln = item["line"]
        self._set_learning_status(
            f"## {item['seq']}  ({pos}/{n_total})   行号: {ln if ln else '—'}"
        )
        # 同步浏览模式 (但不切页)
        if ln and self.lines:
            target = ln - 1
            if 0 <= target < len(self.lines):
                self.current_line = target
                self._show_current_line()
        self._set_status(
            f"切换到学习点 ## {item['seq']}  (第 {ln} 行)" if ln
            else f"切换到学习点 ## {item['seq']}  (无行号)"
        )

    def _jump_source_line(self):
        """学习面板的'跳到浏览页'按钮:把浏览 current_line 设到该学习点对应的行"""
        if self.learning_index is None or not self.learning_items:
            self._set_learning_status("请先选一个学习点。")
            return
        item = self.learning_items[self.learning_index]
        if item["line"] is None:
            messagebox.showinfo("提示", "该学习点没有对应的原文行号。")
            return
        target = item["line"] - 1
        if 0 <= target < len(self.lines):
            self.current_line = target
            self._show_current_line()
            self.notebook.select(0)  # 切到浏览页
            self._set_status(f"→ 浏览模式:第 {target + 1} 行  ({item['target'] or '空目标'})")

    def _render_source_text(self):
        """渲染整个原文到学习面板的“原文区”。
        - 所有学习点位置用淡黄高亮 (learn_point)
        - 当前学习点位置用橙色加粗 (current_point)
        - 其他行正常显示 (灰色行号)
        """
        if self.learn_text is None:
            return
        self.learn_text.config(state=tk.NORMAL)
        self.learn_text.delete("1.0", tk.END)

        # 收集学习点行号 -> item 列表
        learning_lines = {}
        for i, it in enumerate(self.learning_items):
            if it["line"] is not None and 1 <= it["line"] <= len(self.lines):
                learning_lines.setdefault(it["line"], []).append(i)

        # 当前学习点行号
        current_line = None
        if self.learning_index is not None:
            ci = self.learning_items[self.learning_index]
            if ci["line"]:
                current_line = ci["line"]

        # 渲染每行 + 记录 “原文行号 -> Text行号” 映射
        self._learn_line_to_text = {}
        text_line = 1
        for i, line_text in enumerate(self.lines):
            lineno = i + 1
            body = line_text.rstrip("\n") or "（空行）"
            prefix = f"{lineno:4d} │ "
            self._learn_line_to_text[lineno] = text_line

            if lineno in learning_lines:
                count = len(learning_lines[lineno])
                is_current = (lineno == current_line)
                if is_current:
                    # 当前学习点:橙色背景 + 白字 + 加粗 (加 ▶ 标记)
                    self.learn_text.insert(tk.END, "▶ ", "current_marker")
                    self.learn_text.insert(tk.END, prefix, "current_marker")
                    self.learn_text.insert(tk.END, body + "\n", "current_point")
                else:
                    # 其他学习点:淡黄背景 + 行号灰色 + • 标记
                    self.learn_text.insert(tk.END, "• ", "learn_marker")
                    self.learn_text.insert(tk.END, prefix, "line_no")
                    self.learn_text.insert(tk.END, body + "\n", "learn_point")
            else:
                # 普通行
                self.learn_text.insert(tk.END, "   ", "line_no")
                self.learn_text.insert(tk.END, prefix, "line_no")
                self.learn_text.insert(tk.END, body + "\n")
            text_line += 1

        self.learn_text.config(state=tk.DISABLED)

        # 滚动到当前学习点位置 (预留几行上文)
        if current_line is not None and current_line in self._learn_line_to_text:
            txt_line = self._learn_line_to_text[current_line]
            target = max(1, txt_line - 3)
            self.learn_text.see(f"{target}.0")

    def _render_explanation(self):
        """渲染当前学习点的解释到“当前学习点解释区”。"""
        if self.learn_explain is None:
            return
        self.learn_explain.config(state=tk.NORMAL)
        self.learn_explain.delete("1.0", tk.END)

        if self.learning_index is None or not self.learning_items:
            self._exp_insert("(请先加载单词本文件)\n", "empty")
            self.learn_explain.config(state=tk.DISABLED)
            return

        item = self.learning_items[self.learning_index]
        seq = item["seq"]
        ln = item["line"]
        target = item["target"]

        # 头部: 序号 + 行号
        head = f"## {seq}"
        if ln:
            head += f"  •  第 {ln} 行"
        self._exp_insert(head + "\n", "seq_tag")
        self._exp_insert(target or "（本条无目标文本）", "target")
        self._exp_insert("\n\n")

        sections = item["sections"]
        if sections:
            for title, body in sections:
                self._exp_insert(f"▌ {title}\n", "heading")
                if body.strip():
                    for sub in body.split("\n"):
                        if re.match(r"^\s*\d+[\.、]", sub):
                            self._exp_insert(sub + "\n", "numbered")
                        else:
                            self._exp_insert(sub + "\n")
                    self._exp_insert("\n")
        else:
            self._exp_insert("(本条尚无解释内容)\n", "empty")

        self.learn_explain.see("1.0")
        self.learn_explain.config(state=tk.DISABLED)

    def _exp_insert(self, text, tag=None):
        if tag:
            self.learn_explain.insert(tk.END, text, (tag,))
        else:
            self.learn_explain.insert(tk.END, text)

    # 保留旧接口作为别名,以防其他位置被调用 (无害)
    def _update_learning_view(self):
        self._render_source_text()
        self._render_explanation()

    def _insert_learn_text(self, text, tag=None):
        self._exp_insert(text, tag)

    # -------------------------------------------------------------- 浏览
    def _show_current_line(self):
        if not self.lines:
            return
        if self.current_line < 0:
            self.current_line = 0
        if self.current_line >= len(self.lines):
            self.current_line = len(self.lines) - 1

        total = len(self.lines)
        ctx = self.context_size
        start = max(0, self.current_line - ctx)
        end = min(total, self.current_line + ctx + 1)

        self.line_label.config(
            text=(
                f"当前: 第 {self.current_line + 1} / {total} 行  •  "
                f"显示上下文 {start + 1}–{end} 行 (共 {end - start} 行)"
            )
        )

        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete("1.0", tk.END)

        # 同步同步: vsync = True 保证插入、tag 都生效
        for i in range(start, end):
            line = self.lines[i].rstrip("\n") or "（空行）"
            is_current = (i == self.current_line)
            marker = "▶" if is_current else " "
            prefix = f"{marker} {i+1:4d} │ "
            tag_now = ("current_line" if is_current else "context_line",)

            self.text_widget.insert(tk.END, prefix, ("line_prefix",) + tag_now)
            self.text_widget.insert(tk.END, line + "\n", tag_now)

        # 让当前行尽量在可见区域中间
        self.text_widget.see(f"{ (self.current_line - start) + 1 }.0")

        self.text_widget.config(state=tk.DISABLED)
        self._set_status(f"第 {self.current_line + 1} 行")

    def _set_context_size(self, n: int):
        """修改上下文行数,重新渲染"""
        self.context_size = n
        self.context_size_var.set(n)
        self._show_current_line()

    def _build_section_index(self):
        """扫描 A1-01 / A2-12 之类的集标题,作为跳转错点"""
        import re
        pat = re.compile(r"^([AB]\d-\d{2})-[^\n]+$")
        self.section_indices = []
        for i, line in enumerate(self.lines):
            stripped = line.strip()
            m = pat.match(stripped)
            if m:
                self.section_indices.append((i, m.group(1)))

    def _jump_to_section(self, direction: int):
        """direction=-1 上一集, +1 下一集"""
        if not self.section_indices:
            self._set_status("未找到集标题。")
            return
        if direction > 0:
            for line_no, name in self.section_indices:
                if line_no > self.current_line:
                    self.current_line = line_no
                    self._show_current_line()
                    self._set_status(f"→ {name}  (第 {line_no + 1} 行)")
                    return
            self._set_status("已经是最后一集。")
        else:
            prev = None
            for line_no, name in self.section_indices:
                if line_no < self.current_line:
                    prev = (line_no, name)
                else:
                    break
            if prev:
                self.current_line = prev[0]
                self._show_current_line()
                self._set_status(f"← {prev[1]}  (第 {prev[0] + 1} 行)")
            else:
                self._set_status("已经是第一集。")

    def _prev_line(self):
        """上一段:向后跳 context_size 行;如选了 ±10 则一次跳 10 行"""
        new_line = max(0, self.current_line - self.context_size)
        if new_line != self.current_line:
            self.current_line = new_line
            self._show_current_line()

    def _next_line(self):
        """下一段:向前跳 context_size 行"""
        max_line = len(self.lines) - 1
        new_line = min(max_line, self.current_line + self.context_size)
        if new_line != self.current_line:
            self.current_line = new_line
            self._show_current_line()

    def _step_one(self, delta: int):
        """只动 1 行,用于精确读取某一行"""
        max_line = len(self.lines) - 1
        new_line = max(0, min(max_line, self.current_line + delta))
        if new_line != self.current_line:
            self.current_line = new_line
            self._show_current_line()

    def _goto_start(self):
        self.current_line = 0
        self._show_current_line()

    def _goto_end(self):
        self.current_line = len(self.lines) - 1
        self._show_current_line()

    def _goto_line(self):
        if not self.lines:
            return
        try:
            v = int(self.jump_entry.get().strip())
        except ValueError:
            messagebox.showinfo("提示", "请输入有效的行号（整数）")
            return
        total = len(self.lines)
        if 1 <= v <= total:
            self.current_line = v - 1
            self._show_current_line()
        else:
            messagebox.showwarning("范围错误", f"行号必须在 1~{total} 之间")

    def _find_word(self):
        if not self.lines:
            return
        win = tk.Toplevel(self.root)
        win.title("查找词")
        win.geometry("360x100")
        win.transient(self.root)
        win.grab_set()
        ttk.Label(win, text="输入词（区分大小写）：").pack(padx=8, pady=(8, 2), anchor=tk.W)
        entry = ttk.Entry(win)
        entry.pack(fill=tk.X, padx=8)
        entry.focus_set()

        def _do_search():
            keyword = entry.get().strip()
            if not keyword:
                return
            start = self.current_line
            total = len(self.lines)
            for offset in range(1, total):
                i = (start + offset) % total
                if keyword in self.lines[i]:
                    self.current_line = i
                    self._show_current_line()
                    win.destroy()
                    return
            messagebox.showinfo("未找到", f"全文未找到:{keyword!r}")

        entry.bind("<Return>", lambda e: _do_search())
        ttk.Button(win, text="查找下一处", command=_do_search).pack(pady=8)

    # -------------------------------------------------------------- 提取
    def _extract_selection(self):
        import re
        # 1. 先检查选区是否有效
        try:
            sel_ranges = self.text_widget.tag_ranges("sel")
            sel = self.text_widget.selection_get()
        except tk.TclError:
            self._set_status("没有选中的文字。请先用鼠标拖选要提取的内容。")
            return
        if not sel_ranges:
            self._set_status("没有选中的文字。请先用鼠标拖选要提取的内容。")
            return

        # 2. 从选区起点算出“实际选中的原文行号” (而不是 current_line)
        #    text_widget 的第 1 行对应上下文窗口的 view_start 行
        start_index = str(sel_ranges[0])            # 形如 "3.5"
        try:
            start_line_in_widget = int(start_index.split(".")[0])  # widget 中第几行 (1-based)
        except (ValueError, IndexError):
            start_line_in_widget = 1
        view_start = max(0, self.current_line - self.context_size)
        actual_line = view_start + (start_line_in_widget - 1)        # 0-based 原文行号
        if actual_line < 0:
            actual_line = 0
        if actual_line >= len(self.lines):
            actual_line = len(self.lines) - 1
        # 同步 current_line 到“实际选中”的行,便于跳转浏览 + 后续提取记录正确行号
        self.current_line = actual_line

        # 3. 选择跨多行:只取第一行
        if "\n" in sel:
            sel = sel.split("\n", 1)[0]
            self._set_status("选择跨多行:只取第一行。")

        # 4. 去掉行号前缀 "▶ NNNN │ " (即使选中了前缘,这里也能处理)
        m = re.match(r"^[\s▶]?\s*\d+\s*│\s*(.*)$", sel)
        if m:
            sel = m.group(1)

        sel = " ".join(sel.split())
        if not sel:
            self._set_status("选中的内容为空。")
            return
        # 5. 重新渲染上下文窗口 (current_line 已经修正),保证选区跟行号一致
        self._show_current_line()
        self._add_word(sel)

    def _extract_whole_line(self):
        line = self.lines[self.current_line].rstrip("\n").strip()
        if not line:
            self._set_status("当前行为空。")
            return
        self._add_word(line)

    def _add_word(self, word: str):
        if self.dedupe_var.get():
            existing = [w for w, _ in self.words]
            if word in existing:
                self._set_status(f"已存在,跳过:{word!r}")
                return
        ln = self.current_line + 1
        self.words.append((word, ln))
        self.listbox.insert(tk.END, f"{word}    ← 第 {ln} 行")
        self._update_word_count()
        self._set_status(f"✓ 已提取:{word!r}  (第 {ln} 行)")
        self._persist_words()  # 立刻写入磁盘, 防止丢失
        if self.autonext_var.get():
            self._next_line()

    # -------------------------------------------------------------- 持久化
    def _persist_words(self):
        """把当前提取的生词写入磁盘 JSON,程序崩溃/重启不丢数据。"""
        import json
        try:
            data = {
                "source_basename": os.path.basename(self.source_path) if self.source_path else "",
                "words": [{"word": w, "line": ln} for w, ln in self.words],
            }
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # 静默失败, 仅状态栏提示, 不阻塞主流程
            try:
                self._set_status(f"持久化失败:{e}")
            except Exception:
                pass

    def _load_persisted_words(self):
        """启动时加载上次的提取:仅在 source_basename 一致时恢复,避免跨脚本串词。"""
        import json
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        if not isinstance(data, dict):
            return
        cur_base = os.path.basename(self.source_path) if self.source_path else ""
        if data.get("source_basename") != cur_base:
            return
        loaded = 0
        for entry in data.get("words", []):
            w = entry.get("word", "")
            ln = entry.get("line", 0)
            if w:
                self.words.append((w, ln))
                self.listbox.insert(tk.END, f"{w}    ← 第 {ln} 行")
                loaded += 1
        if loaded:
            self._update_word_count()
            self._set_status(f"已恢复上次提取的 {loaded} 个生词")

    # -------------------------------------------------------------- 列表操作
    def _delete_selected(self):
        idx = self.listbox.curselection()
        if not idx:
            return
        i = idx[0]
        word = self.words[i][0]
        if not messagebox.askyesno("删除确认", f"删除生词?\n\n  {word!r}"):
            return
        del self.words[i]
        self.listbox.delete(i)
        self._update_word_count()
        self._set_status(f"已删除:{word!r}")
        self._persist_words()

    def _move_item(self, delta: int):
        idx = self.listbox.curselection()
        if not idx:
            return
        i = idx[0]
        j = i + delta
        if not (0 <= j < len(self.words)):
            return
        self.words[i], self.words[j] = self.words[j], self.words[i]
        self._refresh_listbox()
        self.listbox.selection_set(j)
        self.listbox.activate(j)
        self._persist_words()

    def _refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for w, ln in self.words:
            self.listbox.insert(tk.END, f"{w}    ← 第 {ln} 行")

    def _clear_all(self):
        if not self.words:
            return
        if not messagebox.askyesno("清空确认", f"清空全部 {len(self.words)} 个生词?"):
            return
        self.words.clear()
        self.listbox.delete(0, tk.END)
        self._update_word_count()
        self._set_status("已清空全部生词")
        self._persist_words()

    # -------------------------------------------------------------- 导出
    def _save_words(self):
        """导出已提取的生词到 txt 文件。

        改进点 (2026-07):
        - 默认输出到「桌面」目录, 一眼能找到
        - 使用 utf-8-sig (BOM) 编码, Windows 记事本直接打开不乱码
        - 导出按行号排序, 方便按原文顺序复习
        - 导出后自动用系统默认程序打开
        """
        if not self.words:
            messagebox.showinfo("提示", "还没有提取任何单词。\n\n请先在原文里选中词,再点击 [提取所选词]。")
            return

        # 1) 默认保存位置: 优先桌面, 没有桌面则脚本目录
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.isdir(desktop):
            desktop = self.script_dir

        # 2) 文件名 (按源文件+时间, 避免重复)
        src_base = os.path.splitext(os.path.basename(self.source_path))[0]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"{src_base} 生词本 {ts}.txt"

        path = filedialog.asksaveasfilename(
            title="保存生词到 txt 文件",
            defaultextension=".txt",
            initialfile=default_name,
            initialdir=desktop,
            filetypes=[("Text (推荐)", "*.txt"), ("All", "*.*")],
        )
        if not path:
            self._set_status("已取消保存。")
            return

        # 3) 按行号排序后写出
        try:
            sorted_words = sorted(self.words, key=lambda x: (x[1], x[0]))
            src_name = os.path.basename(self.source_path)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(path, "w", encoding="utf-8-sig", newline="\n") as f:
                f.write(f"# Nicos Weg A1 生词本\n")
                f.write(f"# 来源: {src_name}\n")
                f.write(f"# 导出时间: {now_str}\n")
                f.write(f"# 共 {len(self.words)} 个词 / 词组 (按原文行号排序)\n")
                f.write("# " + "=" * 60 + "\n\n")
                for i, (w, ln) in enumerate(sorted_words, 1):
                    f.write(f"{i:3d}. {w}    (原文第 {ln} 行)\n")
            size = os.path.getsize(path)
            self._set_status(f"💾 已保存 {len(self.words)} 个生词 → {path} ({size} 字节)")
            # 4) 自动用系统默认程序打开
            try:
                os.startfile(path)
            except Exception:
                pass  # 非 Windows / 没有默认程序时静默跳过
            messagebox.showinfo("保存成功", f"生词本已保存到:\n\n{path}\n\n共 {len(self.words)} 个词,已按原文行号排序。")
        except Exception as e:
            messagebox.showerror("保存失败", f"保存到 {path} 失败:\n\n{e}")
            self._set_status(f"❌ 保存失败: {e}")

    def _copy_to_clipboard(self):
        if not self.words:
            return
        text = "\n".join(w for w, _ in self.words)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._set_status("📋 已复制全部到剪贴板")

    # -------------------------------------------------------------- 辅助
    def _update_word_count(self):
        self.word_count_label.config(text=f"已提取: {len(self.words)} 个")

    def _set_status(self, msg: str):
        self.status_bar.config(text=msg)


def main():
    root = tk.Tk()
    try:
        # 尝试使用 Windows 主题
        root.tk.call("source", "sun-valley.tcl")
    except tk.TclError:
        pass
    WordExtractor(root)
    root.mainloop()


if __name__ == "__main__":
    main()



