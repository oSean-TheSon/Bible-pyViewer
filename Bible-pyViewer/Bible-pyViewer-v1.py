from pathlib import Path
import json
import math
import random
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua",
    "Judges", "Ruth", "1Samuel", "2Samuel", "1Kings", "2Kings",
    "1Chronicles", "2Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
    "Psalms", "Proverbs", "Ecclesiastes", "SongofSolomon", "Isaiah",
    "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel",
    "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
    "Zephaniah", "Haggai", "Zechariah", "Malachi", "Matthew", "Mark",
    "Luke", "John", "Acts", "Romans", "1Corinthians", "2Corinthians",
    "Galatians", "Ephesians", "Philippians", "Colossians",
    "1Thessalonians", "2Thessalonians", "1Timothy", "2Timothy",
    "Titus", "Philemon", "Hebrews", "James", "1Peter", "2Peter",
    "1John", "2John", "3John", "Jude", "Revelation",
]

STOP_WORDS = set("""
a about above after again against all am an and any are as at be because
been before being below between both but by can could did do does doing
down during each few for from had has have having he her here hers
herself him himself his how i if in into is it its itself just me more most
my myself no nor not of off on once only or other our ours ourselves out
over own same she should so some such than that the their theirs them
themselves then there these they this those through to too under until up
very was we were what when where which while who whom why will with would
you your yours yourself yourselves thee thou thy thine ye hath hast art
unto upon
""".split())

TEAL = "#5d7c7c"
SILVER = "#c0c0c0"
MID = "#d4d0c8"
WHITE = "#ffffff"
DARK = "#808080"
BLACK = "#000000"
ACCENT = "#a84f3e"
ACCENT_DARK = "#71372f"
UI_FONT = ("Tahoma", 9)
SERIF_FONT = ("Georgia", 12)

VERSES_PER_PAGE = 20
SEARCH_RESULTS_PER_PAGE = 50
SEARCH_BATCH_SIZE = 250


class BibleViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Bible Viewer")
        self.root.geometry("1000x800")
        self.root.minsize(1000, 800)
        self.root.configure(bg=TEAL)

        self.bible = {}
        self.folder_path = None
        self.current_book = "Genesis"
        self.current_chapter = 0
        self.current_page = 0
        self.current_view = "Home"

        self._search_token = 0

        self._build_window()
        self.render_home()

    def _draw_titlebar_gradient(self, canvas, event=None):
        """Draw a left-to-right gradient on the title bar."""
        width = canvas.winfo_width()
        height = canvas.winfo_height()

        if width < 2 or height < 1:
            return

        start_rgb = tuple(
            int(ACCENT_DARK[i:i + 2], 16) for i in (1, 3, 5)
        )
        end_rgb = tuple(
            int(ACCENT[i:i + 2], 16) for i in (1, 3, 5)
        )

        canvas.delete("gradient")

        for x in range(width):
            ratio = x / (width - 1)
            rgb = tuple(
                round(start + (end - start) * ratio)
                for start, end in zip(start_rgb, end_rgb)
            )
            color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            canvas.create_line(
                x, 0, x, height,
                fill=color,
                tags="gradient",
            )

        # Keep the gradient behind the title and controls.
        canvas.tag_lower("gradient")

    def _on_titlebar_resize(self, canvas, event):
        """Redraw the gradient and keep controls at the right edge."""
        self._draw_titlebar_gradient(canvas, event)
        canvas.coords("titlebar_controls", event.width - 5, 15)

    def _build_window(self):
        self.window = tk.Frame(
            self.root, bg=SILVER, bd=2, relief="raised"
        )
        self.window.pack(fill="both", expand=True, padx=90, pady=55)

        titlebar = tk.Canvas(
            self.window,
            height=30,
            highlightthickness=0,
            bd=0,
        )
        titlebar.pack(fill="x")
        titlebar.pack_propagate(False)

        titlebar.create_text(
            8, 15,
            text="✝ Bible Viewer",
            fill=WHITE,
            font=("Tahoma", 9, "bold"),
            anchor="w",
        )

        controls = tk.Frame(titlebar, bg=ACCENT)
        for symbol in ("_", "□", "+"):
            tk.Label(
                controls,
                text=symbol,
                width=2,
                bg=SILVER,
                fg=BLACK,
                font=("Tahoma", 8, "bold"),
                relief="raised",
                bd=2,
            ).pack(side="left", padx=1)

        titlebar.create_window(
            0, 15,
            window=controls,
            anchor="e",
            tags="titlebar_controls",
        )

        titlebar.bind(
            "<Configure>",
            lambda event: self._on_titlebar_resize(titlebar, event),
        )

        self._build_menus()
        tk.Frame(self.window, bg=DARK, height=1).pack(fill="x", padx=5)

        toolbar = tk.Frame(self.window, bg=SILVER)
        toolbar.pack(fill="x", padx=8, pady=7)

        for label, command in [
            ("Home", self.render_home),
            ("Contents", self.show_contents),
            ("Read", self.open_reader),
            ("Search", self.show_search),
            ("Random Verse", self.show_random_verse),
            ("Word Cloud", self.show_cloud),
            ("Statistics", self.show_statistics),
        ]:
            tk.Button(
                toolbar,
                text=label,
                command=command,
                bg=MID,
                font=UI_FONT,
                relief="raised",
                bd=2,
                padx=7,
                pady=3,
            ).pack(side="left", padx=(0, 5))

        # Pack the status row before the expandable content frame so it
        # retains its space at the bottom of the window.
        status_row = tk.Frame(self.window, bg=SILVER)
        status_row.pack(
            side="bottom", fill="x", padx=5, pady=(0, 5)
        )

        self.status = tk.Label(
            status_row,
            text="",
            bg=SILVER,
            fg=BLACK,
            anchor="w",
            font=("Tahoma", 8),
            relief="sunken",
            bd=2,
            padx=7,
            pady=3,
        )
        self.status.pack(side="left", fill="x", expand=True)

        tk.Label(
            status_row,
            text="✝",
            bg=SILVER,
            fg=BLACK,
            font=("Georgia", 13, "bold"),
            padx=8,
        ).pack(side="right")

        self.content = tk.Frame(
            self.window,
            bg=WHITE,
            bd=2,
            relief="sunken",
        )
        self.content.pack(fill="both", expand=True, padx=12, pady=10)

    def _build_menus(self):
        menubar = tk.Frame(self.window, bg=SILVER)
        menubar.pack(fill="x", padx=4, pady=(3, 1))

        menus = [
            ("File", [
                ("Load Bible folder…", self.load_folder),
                ("Home — Random Verse", self.render_home),
                ("Close current view", self.render_home),
            ]),
            ("View", [
                ("Table of Contents", self.show_contents),
                ("Read the Bible", self.open_reader),
                ("Random Verse", self.show_random_verse),
            ]),
            ("Tools", [
                ("Search the Bible", self.show_search),
                ("Word Cloud", self.show_cloud),
                ("Statistics", self.show_statistics),
            ]),
            ("Help", [("About Bible Viewer", self.show_about)]),
        ]

        for title, items in menus:
            menu = tk.Menu(
                self.root,
                tearoff=False,
                bg=SILVER,
                fg=BLACK,
                activebackground=ACCENT,
                activeforeground=WHITE,
                font=UI_FONT,
            )

            for label, command in items:
                menu.add_command(label=label, command=command)

            menu.bind(
                "<Unmap>",
                lambda event, current_menu=menu:
                    self._clear_open_menu(current_menu),
                add="+",
            )

            button = tk.Button(
                menubar,
                text=title,
                bg=SILVER,
                font=UI_FONT,
                relief="flat",
                padx=10,
                pady=4,
            )
            button.configure(
                command=lambda m=menu, b=button: self._post_menu(m, b)
            )
            button.pack(side="left")

    def _post_menu(self, menu, button):
        # Clicking the button for the open menu closes it.
        if getattr(self, "_open_menu", None) is menu:
            menu.unpost()
            self._open_menu = None
            return

        # Close a different menu before opening this one.
        open_menu = getattr(self, "_open_menu", None)
        if open_menu is not None:
            open_menu.unpost()

        self._open_menu = menu

        try:
            menu.tk_popup(
                button.winfo_rootx(),
                button.winfo_rooty() + button.winfo_height(),
            )
        finally:
            menu.grab_release()

    def _clear_open_menu(self, menu):
        if getattr(self, "_open_menu", None) is menu:
            self._open_menu = None
    

    def _set_view(self, name):
        self.current_view = name
        count = len(self.loaded_books())
        if count:
            noun = "book" if count == 1 else "books"
            text = f"Ready | {count} {noun} loaded | {name}"
        else:
            text = f"Ready | No Bible folder loaded | {name}"
        self.status.config(text=text)

    def _clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def _label(self, parent, text, font=UI_FONT, **kwargs):
        return tk.Label(
            parent, text=text, bg=kwargs.pop("bg", WHITE),
            fg=kwargs.pop("fg", BLACK), font=font,
            justify=kwargs.pop("justify", "left"),
            wraplength=kwargs.pop("wraplength", 760), **kwargs,
        )

    def _make_scrollable(self, parent, background=WHITE):
        """Create a vertically scrollable frame without accumulating bindings."""
        holder = tk.Frame(parent, bg=background)
        canvas = tk.Canvas(holder, bg=background, highlightthickness=0)
        scrollbar = tk.Scrollbar(
            holder, orient="vertical", command=canvas.yview
        )
        inner = tk.Frame(canvas, bg=background)
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_inner(event):
            canvas.itemconfigure(window_id, width=event.width)

        inner.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_inner)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def wheel(event):
            if getattr(event, "delta", 0):
                canvas.yview_scroll(int(-event.delta / 120), "units")
            elif getattr(event, "num", None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(1, "units")

        def bind_wheel(_event=None):
            canvas.bind_all("<MouseWheel>", wheel)
            canvas.bind_all("<Button-4>", wheel)
            canvas.bind_all("<Button-5>", wheel)

        def unbind_wheel(_event=None):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", bind_wheel)
        canvas.bind("<Leave>", unbind_wheel)
        return holder, inner

    # ---------- Bible data ----------

    def loaded_books(self):
        return [book for book in BOOKS if book in self.bible]

    def _require_bible(self):
        if self.loaded_books():
            return True
        messagebox.showinfo(
            "Bible Viewer",
            "Load the Bible folder first using File → Load Bible folder…",
        )
        return False

    def load_folder(self):
        folder = filedialog.askdirectory(title="Select Bible JSON folder")
        if not folder:
            return

        folder_path = Path(folder)
        loaded = {}

        for path in folder_path.glob("*.json"):
            if path.stem not in BOOKS:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("chapters"), list):
                    loaded[path.stem] = data
                else:
                    print(
                        f"Skipping {path.name}: "
                        "expected a JSON object with chapters list."
                    )
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                print(f"Could not read {path.name}: {error}")

        self.folder_path = folder_path
        self.bible = loaded

        if self.loaded_books():
            self.current_book = self.loaded_books()[0]
            self.current_chapter = 0
            self.current_page = 0
            self.render_home()
        else:
            self._set_view("Home")
            self._clear_content()
            self._label(
                self.content, "No Bible books found", ("Tahoma", 15, "bold"),
                pady=(35, 8),
            ).pack(anchor="w", padx=16)
            self._label(
                self.content,
                "Select a folder containing files named like "
                "Genesis.json and Matthew.json.",
            ).pack(anchor="w", padx=16)

    def _chapters(self, book):
        data = self.bible.get(book, {})
        chapters = data.get("chapters", [])
        return chapters if isinstance(chapters, list) else []

    def _chapter_number(self, book, chapter_index):
        chapters = self._chapters(book)
        if not 0 <= chapter_index < len(chapters):
            return chapter_index + 1
        chapter = chapters[chapter_index]
        if isinstance(chapter, dict):
            return chapter.get("chapter", chapter_index + 1)
        return chapter_index + 1

    def _chapter_verses(self, chapter):
        if not isinstance(chapter, dict):
            return []
        verses = chapter.get("verses", [])
        if not isinstance(verses, list):
            return []

        result = []
        for index, verse in enumerate(verses):
            if isinstance(verse, dict):
                result.append({
                    "verse": verse.get("verse", index + 1),
                    "text": str(verse.get("text", "")),
                })
        return result

    def _iter_verses(self, book):
        """Yield verses lazily so searches can process them in small batches."""
        for chapter_index, chapter in enumerate(self._chapters(book)):
            chapter_number = self._chapter_number(book, chapter_index)
            for verse in self._chapter_verses(chapter):
                yield {
                    "book": book,
                    "chapter": chapter_number,
                    "verse": verse["verse"],
                    "text": verse["text"],
                }

    def _verses(self, book):
        return list(self._iter_verses(book))

    # ---------- Home and contents ----------

    def render_home(self):
        self._search_token += 1
        self._set_view("Home")
        if self.loaded_books():
            self.show_random_verse()
            return

        self._clear_content()
        welcome = tk.Frame(self.content, bg=WHITE)
        welcome.pack(expand=True)

        self._label(
            welcome, "Welcome to Bible Viewer", ("Tahoma", 17, "bold")
        ).pack(pady=(0, 12))
        self._label(
            welcome,
            "Read, search, and explore the King James Bible.\n\n"
            "Choose File → Load Bible folder… and select the folder "
            "containing the Bible book JSON files.",
            justify="center", wraplength=520,
        ).pack(pady=(0, 14))
        tk.Button(
            welcome, text="Load Bible folder…", command=self.load_folder,
            bg=MID, font=UI_FONT, relief="raised", bd=2, padx=10, pady=4,
        ).pack()

    def show_random_verse(self):
        self._search_token += 1
        self._set_view("Random Verse")
        if not self._require_bible():
            return

        verses = [
            verse
            for book in self.loaded_books()
            for verse in self._iter_verses(book)
        ]
        self._clear_content()

        if not verses:
            self._label(
                self.content, "No verses found", ("Tahoma", 15, "bold")
            ).pack(anchor="w", padx=20, pady=(25, 8))
            self._label(
                self.content, "The loaded files contain no verse data."
            ).pack(anchor="w", padx=20)
            return

        verse = random.choice(verses)
        card = tk.Frame(
            self.content, bg="#fffef4", bd=2, relief="groove",
            padx=24, pady=20,
        )
        card.pack(fill="x", padx=35, pady=35)

        self._label(
            card, "Random Bible Verse", ("Tahoma", 15, "bold"),
            bg="#fffef4",
        ).pack(anchor="w", pady=(0, 12))

        self._label(
            card, f"{verse['book']} {verse['chapter']}:{verse['verse']}",
            ("Tahoma", 10, "bold"), bg="#fffef4", fg=ACCENT,
        ).pack(anchor="w", pady=(0, 12))

        verse_label = self._label(
            card, verse["text"], ("Georgia", 16), bg="#fffef4",
            wraplength=600,
        )
        verse_label.pack(fill="x", anchor="w", pady=(0, 20))

        tk.Button(
            card, text="Another verse", command=self.show_random_verse,
            bg=MID, font=UI_FONT, relief="raised", bd=2, padx=10, pady=4,
        ).pack(anchor="w")
    def show_contents(self):
        self._search_token += 1
        self._set_view("Contents")
        if not self._require_bible():
            return
        self._clear_content()

        self._label(
            self.content, "Table of Contents", ("Tahoma", 15, "bold")
        ).pack(anchor="w", padx=16, pady=(12, 6))

        holder, inner = self._make_scrollable(self.content)
        holder.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        books = self.loaded_books()
        groups = [
            ("Old Testament", [b for b in books if BOOKS.index(b) < 39]),
            ("New Testament", [b for b in books if BOOKS.index(b) >= 39]),
        ]
        for heading, subset in groups:
            if not subset:
                continue
            self._label(
                inner, heading, ("Tahoma", 11, "bold")
            ).pack(anchor="w", padx=8, pady=(8, 5))
            grid = tk.Frame(inner, bg=WHITE)
            grid.pack(fill="x", padx=6)
            for index, book in enumerate(subset):
                tk.Button(
                    grid, text=book, anchor="w",
                    command=lambda b=book: self.open_reader(b, 0),
                    bg=MID, font=UI_FONT, relief="raised", bd=2,
                ).grid(
                    row=index // 4, column=index % 4, sticky="ew",
                    padx=3, pady=3,
                )
            for column in range(4):
                grid.columnconfigure(column, weight=1)

    # ---------- Reader ----------

    def open_reader(self, book=None, chapter_index=None, page=None):
        self._search_token += 1
        if not self._require_bible():
            return

        available = self.loaded_books()
        book = book or self.current_book
        if book not in self.bible:
            book = available[0]

        chapters = self._chapters(book)
        if not chapters:
            self._set_view(f"Read | {book}")
            self._clear_content()
            self._label(
                self.content, f"{book} has no chapter data.",
                ("Tahoma", 13, "bold"),
            ).pack(anchor="w", padx=20, pady=20)
            return

        if chapter_index is None:
            chapter_index = self.current_chapter
        chapter_index = max(0, min(int(chapter_index), len(chapters) - 1))

        all_verses = list(self._iter_verses(book))
        if page is None:
            selected_chapter = self._chapter_number(book, chapter_index)
            start_index = next(
                (
                    i for i, verse in enumerate(all_verses)
                    if verse["chapter"] == selected_chapter
                ),
                0,
            )
            current_page = start_index // VERSES_PER_PAGE
        else:
            current_page = max(0, int(page))

        page_count = max(1, math.ceil(len(all_verses) / VERSES_PER_PAGE))
        current_page = min(current_page, page_count - 1)
        start = current_page * VERSES_PER_PAGE
        end = min(start + VERSES_PER_PAGE, len(all_verses))
        page_verses = all_verses[start:end]

        self.current_book = book
        self.current_page = current_page

        if page_verses:
            displayed_chapter = page_verses[0]["chapter"]
            for index in range(len(chapters)):
                if self._chapter_number(book, index) == displayed_chapter:
                    chapter_index = index
                    break
        self.current_chapter = chapter_index

        chapter_number = self._chapter_number(book, chapter_index)
        self._set_view(f"Read | {book} {chapter_number}")
        self._clear_content()

        controls = tk.Frame(
            self.content, bg=SILVER, bd=2, relief="groove",
            padx=8, pady=8,
        )
        controls.pack(fill="x", padx=8, pady=8)

        tk.Label(
            controls, text="Book:", bg=SILVER,
            font=("Tahoma", 9, "bold"),
        ).pack(side="left")
        book_select = ttk.Combobox(
            controls, values=available, state="readonly", width=18
        )
        book_select.set(book)
        book_select.pack(side="left", padx=(5, 10))
        book_select.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.open_reader(book_select.get(), 0),
        )

        tk.Label(
            controls, text="Chapter:", bg=SILVER,
            font=("Tahoma", 9, "bold"),
        ).pack(side="left")
        chapter_numbers = [
            str(self._chapter_number(book, i))
            for i in range(len(chapters))
        ]
        chapter_select = ttk.Combobox(
            controls, values=chapter_numbers, state="readonly", width=7
        )
        chapter_select.set(str(self._chapter_number(book, chapter_index)))
        chapter_select.pack(side="left", padx=(5, 8))

        def jump_to_chapter(_event=None):
            try:
                selected_index = chapter_numbers.index(chapter_select.get())
            except ValueError:
                selected_index = 0
            self.open_reader(book, selected_index)

        chapter_select.bind("<<ComboboxSelected>>", jump_to_chapter)

        tk.Button(
            controls, text="◀ Previous page",
            command=lambda: self.open_reader(book, page=current_page - 1),
            state="disabled" if current_page == 0 else "normal",
            bg=MID, font=UI_FONT, relief="raised", bd=2,
        ).pack(side="left", padx=(8, 3))
        tk.Button(
            controls, text="Next page ▶",
            command=lambda: self.open_reader(book, page=current_page + 1),
            state="disabled" if current_page >= page_count - 1 else "normal",
            bg=MID, font=UI_FONT, relief="raised", bd=2,
        ).pack(side="left", padx=3)

        text_frame = tk.Frame(self.content, bg=WHITE)
        text_frame.pack(fill="both", expand=True, padx=8, pady=(2, 4))

        text_area = tk.Text(
            text_frame, wrap="word", bg=WHITE, fg=BLACK, font=SERIF_FONT,
            relief="flat", padx=22, pady=12, spacing1=4, spacing3=5,
        )
        scrollbar = tk.Scrollbar(text_frame, command=text_area.yview)
        text_area.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text_area.pack(side="left", fill="both", expand=True)

        heading = f"{book} {self._chapter_number(book, chapter_index)}"
        text_area.insert("end", heading + "\n\n")
        text_area.tag_configure(
            "heading", font=("Tahoma", 15, "bold"), spacing3=12
        )
        text_area.tag_add("heading", "1.0", "1.end")
        text_area.tag_configure(
            "verse_number", foreground=ACCENT,
            font=("Tahoma", 8, "bold"),
        )

        if page_verses:
            for verse in page_verses:
                text_area.insert(
                    "end",
                    f"{verse['chapter']}:{verse['verse']} ",
                    "verse_number",
                )
                text_area.insert("end", f"{verse['text']}\n")
        else:
            text_area.insert("end", "No verses found in this book.")
        text_area.configure(state="disabled")

        bottom_nav = tk.Frame(self.content, bg=WHITE)
        bottom_nav.pack(fill="x", padx=8, pady=(3, 8))

        tk.Button(
            bottom_nav, text="◀ Previous page",
            command=lambda: self.open_reader(book, page=current_page - 1),
            state="disabled" if current_page == 0 else "normal",
            bg=MID, font=UI_FONT, relief="raised", bd=2,
        ).pack(side="left")
        tk.Label(
            bottom_nav, text=f"Page {current_page + 1} of {page_count}",
            bg=WHITE, font=UI_FONT,
        ).pack(side="left", padx=12)
        tk.Button(
            bottom_nav, text="Next page ▶",
            command=lambda: self.open_reader(book, page=current_page + 1),
            state="disabled" if current_page >= page_count - 1 else "normal",
            bg=MID, font=UI_FONT, relief="raised", bd=2,
        ).pack(side="right")

    # ---------- Search ----------

    def show_search(self):
        self._search_token += 1
        self._set_view("Search")
        if not self._require_bible():
            return
        self._clear_content()

        self._label(
            self.content, "Search the Bible", ("Tahoma", 15, "bold")
        ).pack(anchor="w", padx=14, pady=(12, 8))

        row = tk.Frame(
            self.content, bg=SILVER, bd=2, relief="groove",
            padx=8, pady=8,
        )
        row.pack(fill="x", padx=8)

        entry = tk.Entry(row, font=UI_FONT, relief="sunken", bd=2)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 7))

        mode = tk.StringVar(value="exact")
        ttk.Radiobutton(
            row, text="Exact word/phrase", variable=mode, value="exact"
        ).pack(side="left", padx=4)
        ttk.Radiobutton(
            row, text="Contains", variable=mode, value="contains"
        ).pack(side="left", padx=4)

        results = tk.Frame(self.content, bg=WHITE)
        results.pack(fill="both", expand=True, padx=14, pady=8)

        tk.Button(
            row, text="Search",
            command=lambda: self._start_search(
                entry.get(), mode.get(), results
            ),
            bg=MID, font=UI_FONT, relief="raised", bd=2,
        ).pack(side="left", padx=(5, 0))

        self._label(
            self.content,
            "Exact matches whole words or phrases; "
            "Contains also matches inside words.",
            fg="#444",
        ).pack(anchor="w", padx=14, pady=(0, 5))

        entry.bind(
            "<Return>",
            lambda _event: self._start_search(
                entry.get(), mode.get(), results
            ),
        )
        entry.focus_set()

    def _start_search(self, query, mode, results_frame):
        query = query.strip()
        self._search_token += 1
        token = self._search_token

        for widget in results_frame.winfo_children():
            widget.destroy()

        if not query:
            tk.Label(
                results_frame, text="Enter a word or phrase to search.",
                bg=WHITE, fg="#444",
            ).pack(anchor="w", padx=5, pady=5)
            return

        if mode == "exact":
            pattern = re.compile(
                r"(?<!\w)" + re.escape(query) + r"(?!\w)",
                re.IGNORECASE,
            )
        else:
            pattern = re.compile(re.escape(query), re.IGNORECASE)

        status = tk.Label(
            results_frame, text="Searching…", bg=WHITE,
            fg="#444", anchor="w",
        )
        status.pack(anchor="w", padx=5, pady=5)

        books = self.loaded_books()
        book_index = 0
        verse_iterator = iter(self._iter_verses(books[0])) if books else iter(())
        matches = []

        def search_batch():
            nonlocal book_index, verse_iterator

            if token != self._search_token or not results_frame.winfo_exists():
                return

            processed = 0
            try:
                while processed < SEARCH_BATCH_SIZE:
                    try:
                        verse = next(verse_iterator)
                    except StopIteration:
                        book_index += 1
                        if book_index >= len(books):
                            self._show_search_results(
                                results_frame, matches, query, mode, token
                            )
                            return
                        verse_iterator = iter(
                            self._iter_verses(books[book_index])
                        )
                        continue

                    processed += 1
                    if pattern.search(verse["text"]):
                        matches.append(verse)
            except tk.TclError:
                return

            status.config(
                text=f"Searching… {len(matches)} match(es) found so far."
            )
            self.root.after(1, search_batch)

        self.root.after(1, search_batch)

    def _show_search_results(
        self, results_frame, matches, query, mode, token
    ):
        if token != self._search_token or not results_frame.winfo_exists():
            return

        for widget in results_frame.winfo_children():
            widget.destroy()

        if not matches:
            tk.Label(
                results_frame, text="No matching verses found.", bg=WHITE
            ).pack(anchor="w", padx=5, pady=5)
            return

        page_var = tk.IntVar(value=0)
        nav = tk.Frame(results_frame, bg=WHITE)
        nav.pack(fill="x", pady=(0, 5))

        results_holder, results_inner = self._make_scrollable(results_frame)
        results_holder.pack(fill="both", expand=True)

        def draw_page():
            if token != self._search_token or not results_frame.winfo_exists():
                return

            for widget in results_inner.winfo_children():
                widget.destroy()

            page_count = max(
                1, math.ceil(len(matches) / SEARCH_RESULTS_PER_PAGE)
            )
            page = max(0, min(page_var.get(), page_count - 1))
            page_var.set(page)
            start = page * SEARCH_RESULTS_PER_PAGE
            end = min(start + SEARCH_RESULTS_PER_PAGE, len(matches))

            for verse in matches[start:end]:
                tk.Label(
                    results_inner,
                    text=(
                        f"{verse['book']} "
                        f"{verse['chapter']}:{verse['verse']}"
                    ),
                    bg=WHITE, fg=ACCENT, font=("Tahoma", 9, "bold"),
                    anchor="w",
                ).pack(fill="x", padx=5, pady=(5, 0))
                tk.Label(
                    results_inner, text=f"— {verse['text']}", bg=WHITE,
                    fg=BLACK, font=UI_FONT, justify="left", anchor="w",
                    wraplength=760,
                ).pack(fill="x", padx=5, pady=(0, 5))
                tk.Frame(
                    results_inner, bg="#cccccc", height=1
                ).pack(fill="x")

            for widget in nav.winfo_children():
                widget.destroy()

            tk.Label(
                nav,
                text=(
                    f"{len(matches)} result(s) | "
                    f"Page {page + 1} of {page_count}"
                ),
                bg=WHITE, font=("Tahoma", 9, "bold"),
            ).pack(side="left")

            tk.Button(
                nav, text="◀ Previous",
                command=lambda: change_page(page - 1),
                state="disabled" if page == 0 else "normal",
                bg=MID, font=UI_FONT, relief="raised", bd=2,
            ).pack(side="right", padx=(4, 0))
            tk.Button(
                nav, text="Next ▶",
                command=lambda: change_page(page + 1),
                state="disabled" if page >= page_count - 1 else "normal",
                bg=MID, font=UI_FONT, relief="raised", bd=2,
            ).pack(side="right")

        def change_page(new_page):
            page_var.set(new_page)
            draw_page()

        draw_page()

    # ---------- Word cloud ----------

    def show_cloud(self):
        self._search_token += 1
        self._set_view("Word Cloud")
        if not self._require_bible():
            return
        self._clear_content()

        self._label(
            self.content, "Word Cloud", ("Tahoma", 15, "bold")
        ).pack(anchor="w", padx=14, pady=(12, 8))

        row = tk.Frame(
            self.content, bg=SILVER, bd=2, relief="groove",
            padx=8, pady=8,
        )
        row.pack(fill="x", padx=8)

        tk.Label(
            row, text="Book:", bg=SILVER,
            font=("Tahoma", 9, "bold"),
        ).pack(side="left")
        book_var = tk.StringVar(value="Entire Bible")
        book_select = ttk.Combobox(
            row,
            textvariable=book_var,
            values=["Entire Bible", *self.loaded_books()],
            state="readonly",
            width=18,
        )
        book_select.pack(side="left", padx=(4, 12))

        tk.Label(
            row, text="Maximum words:", bg=SILVER,
            font=("Tahoma", 9, "bold"),
        ).pack(side="left")
        max_var = tk.StringVar(value="60")
        max_select = ttk.Combobox(
            row,
            textvariable=max_var,
            values=("40", "60", "80", "100"),
            state="readonly",
            width=6,
        )
        max_select.pack(side="left", padx=(4, 12))

        canvas = tk.Canvas(
            self.content, width=800, height=420, bg=WHITE,
            relief="sunken", bd=2, highlightthickness=0,
        )
        canvas.pack(fill="both", expand=True, padx=12, pady=12)

        def generate():
            try:
                self._generate_cloud(
                    canvas, book_var.get(), int(max_var.get())
                )
            except (TypeError, ValueError) as error:
                messagebox.showerror(
                    "Word Cloud", f"Could not generate cloud:\n{error}"
                )

        tk.Button(
            row, text="Generate", command=generate, bg=MID,
            font=UI_FONT, relief="raised", bd=2,
        ).pack(side="left")
        self.root.after(100, generate)

    def _generate_cloud(self, canvas, selected_book, max_words):
        canvas.delete("all")
        books = (
            self.loaded_books()
            if selected_book == "Entire Bible"
            else [selected_book]
        )
        text = " ".join(
            verse["text"]
            for book in books
            for verse in self._iter_verses(book)
        ).lower()

        counts = {}
        for word in re.findall(
            r"[^\W\d_']+(?:'[^\W\d_']+)*", text, re.UNICODE
        ):
            if len(word) > 2 and word not in STOP_WORDS:
                counts[word] = counts.get(word, 0) + 1

        words = sorted(
            counts.items(), key=lambda item: item[1], reverse=True
        )[:max_words]
        if not words:
            canvas.create_text(
                20, 25, text="No distinctive words to display.",
                anchor="nw", font=("Tahoma", 12),
            )
            return

        canvas.update_idletasks()
        width = max(canvas.winfo_width(), 400)
        height = max(canvas.winfo_height(), 250)
        largest, smallest = words[0][1], words[-1][1]
        placed = []

        for index, (word, count) in enumerate(words):
            size = round(
                15 + 37 * (count - smallest) / max(1, largest - smallest)
            )
            item = canvas.create_text(
                -1000, -1000, text=word,
                font=("Arial", size, "bold"), anchor="nw",
            )
            bbox = canvas.bbox(item)
            if not bbox:
                canvas.delete(item)
                continue

            word_width = bbox[2] - bbox[0]
            word_height = bbox[3] - bbox[1]
            placed_word = False

            for step in range(500):
                angle = step * 0.35 + index * 2.4
                radius = 3 + step * 1.15
                x = width / 2 + math.cos(angle) * radius - word_width / 2
                y = height / 2 + math.sin(angle) * radius - word_height / 2
                box = (x, y, x + word_width, y + word_height)

                if (
                    x < 5 or y < 5
                    or x + word_width > width - 5
                    or y + word_height > height - 5
                ):
                    continue

                collision = any(
                    box[0] < other[2] + 3
                    and box[2] + 3 > other[0]
                    and box[1] < other[3] + 3
                    and box[3] + 3 > other[1]
                    for other in placed
                )
                if collision:
                    continue

                color = (
                    f"#{(index * 43 + 40) % 180 + 40:02x}"
                    f"{90:02x}{140:02x}"
                )
                canvas.coords(item, x, y)
                canvas.itemconfigure(item, fill=color)
                placed.append(box)
                placed_word = True
                break

            if not placed_word:
                canvas.delete(item)

    # ---------- Statistics ----------

    def show_statistics(self):
        self._search_token += 1
        self._set_view("Statistics")
        if not self._require_bible():
            return
        self._clear_content()

        self._label(
            self.content, "Bible Statistics", ("Tahoma", 15, "bold")
        ).pack(anchor="w", padx=14, pady=(12, 8))

        books = self.loaded_books()
        total_chapters = sum(len(self._chapters(book)) for book in books)
        total_verses = sum(
            sum(1 for _ in self._iter_verses(book)) for book in books
        )
        summary = (
            f"Books loaded: {len(books)}\n"
            f"Chapters: {total_chapters}\n"
            f"Verses: {total_verses}"
        )
        self._label(
            self.content, summary, ("Tahoma", 10)
        ).pack(anchor="w", padx=16, pady=(4, 12))

        selector_row = tk.Frame(self.content, bg=WHITE)
        selector_row.pack(anchor="w", padx=14, pady=4)
        tk.Label(
            selector_row, text="Explore a book:", bg=WHITE, font=UI_FONT
        ).pack(side="left", padx=(0, 6))

        selected = tk.StringVar(value=books[0])
        selector = ttk.Combobox(
            selector_row, textvariable=selected, values=books,
            state="readonly", width=22,
        )
        selector.pack(side="left")

        holder, details = self._make_scrollable(self.content)
        holder.pack(fill="both", expand=True, padx=14, pady=8)

        def update_stats(_event=None):
            for widget in details.winfo_children():
                widget.destroy()

            book = selected.get()
            chapters = self._chapters(book)
            verses = self._verses(book)
            word_counts = self._word_counts(verses)
            chapter_lengths = [
                len(self._chapter_verses(chapter))
                for chapter in chapters
            ]
            average = (
                sum(chapter_lengths) / len(chapter_lengths)
                if chapter_lengths else 0
            )

            self._label(
                details,
                f"{book}: {len(chapters)} chapters, {len(verses)} verses\n"
                f"Average verses per chapter: {average:.1f}",
                ("Tahoma", 10, "bold"),
            ).pack(anchor="w", pady=(2, 8))

            common = sorted(
                word_counts.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:12]
            common_text = ", ".join(
                f"{word} ({count})" for word, count in common
            )
            self._label(
                details, "Most frequent distinctive words:",
                ("Tahoma", 9, "bold"),
            ).pack(anchor="w", pady=(4, 2))
            self._label(
                details, common_text or "No words available.",
                wraplength=750,
            ).pack(anchor="w")

            book_words = set(word_counts)
            related = []
            for other in books:
                if other == book:
                    continue
                other_words = set(
                    self._word_counts(self._verses(other))
                )
                union = book_words | other_words
                shared = book_words & other_words
                score = len(shared) / len(union) if union else 0
                related.append((score, other, len(shared)))

            related.sort(reverse=True)
            tk.Label(
                details,
                text="Books with the most vocabulary overlap:",
                bg=WHITE, font=("Tahoma", 9, "bold"),
            ).pack(anchor="w", pady=(12, 2))
            tk.Label(
                details,
                text=(
                    "This is word overlap, not a list of documented "
                    "cross-references."
                ),
                bg=WHITE, fg="#444", font=("Tahoma", 8),
            ).pack(anchor="w", pady=(0, 3))

            for score, other, shared_count in related[:5]:
                tk.Label(
                    details,
                    text=(
                        f"{other} — {shared_count} shared distinctive words "
                        f"({score:.1%} vocabulary overlap)"
                    ),
                    bg=WHITE, anchor="w", font=UI_FONT,
                ).pack(anchor="w")

        selector.bind("<<ComboboxSelected>>", update_stats)
        update_stats()

    def _word_counts(self, verses):
        counts = {}
        for verse in verses:
            for word in re.findall(
                r"[^\W\d_']+(?:'[^\W\d_']+)*",
                verse["text"].lower(),
                re.UNICODE,
            ):
                if len(word) > 2 and word not in STOP_WORDS:
                    counts[word] = counts.get(word, 0) + 1
        return counts

    # ---------- About ----------

    def show_about(self):
        self._search_token += 1
        self._set_view("About")
        self._clear_content()

        self._label(
            self.content,
            "About Bible Viewer",
            ("Tahoma", 15, "bold"),
        ).pack(anchor="w", padx=14, pady=(16, 8))

        about_path = Path(__file__).with_name("about.txt.asc")

        try:
            about_text = about_path.read_text(encoding="utf-8")
        except OSError as exc:
            about_text = f"Could not load About text:\n{exc}"

        self._label(
            self.content,
            about_text,
        ).pack(anchor="w", padx=14)


if __name__ == "__main__":
    root = tk.Tk()
    app = BibleViewer(root)
    root.mainloop()

