"""Modal screens and small shared widgets."""

from __future__ import annotations

from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, SelectionList, Static
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection


class PickMany(ModalScreen[list[str] | None]):
    """Multi-select over a list of strings. Dismisses with the chosen subset."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+a", "all", "Select all"),
        Binding("ctrl+n", "none", "Select none"),
    ]

    def __init__(self, title: str, choices: list[str], selected: list[str], hint: str = "") -> None:
        super().__init__()
        self._title = title
        self._choices = choices
        self._selected = set(selected)
        self._hint = hint or "space toggles · enter accepts · ctrl+a/ctrl+n all/none"

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            if self._choices:
                yield SelectionList(
                    *[Selection(c, c, c in self._selected) for c in self._choices],
                    id="picker",
                )
            else:
                yield Label(Text("nothing to choose from", style="italic"))
            yield Label(self._hint, classes="dialog-hint")

    def on_mount(self) -> None:
        if self._choices:
            self.query_one("#picker", SelectionList).focus()

    def on_key(self, event) -> None:
        if event.key == "enter":
            event.stop()
            self.action_accept()

    def action_accept(self) -> None:
        if not self._choices:
            self.dismiss(None)
            return
        self.dismiss(list(self.query_one("#picker", SelectionList).selected))

    def action_all(self) -> None:
        if self._choices:
            self.query_one("#picker", SelectionList).select_all()

    def action_none(self) -> None:
        if self._choices:
            self.query_one("#picker", SelectionList).deselect_all()

    def action_cancel(self) -> None:
        self.dismiss(None)


class PickOne(ModalScreen[str | None]):
    """Single-select over (value, label) pairs."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, choices: list[tuple[str, str]], hint: str = "") -> None:
        super().__init__()
        self._title = title
        self._choices = choices
        self._hint = hint or "enter picks · esc cancels"

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            yield OptionList(
                *[Option(label, id=value) for value, label in self._choices],
                id="picker",
            )
            yield Label(self._hint, classes="dialog-hint")

    def on_mount(self) -> None:
        self.query_one("#picker", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class AskText(ModalScreen[str | None]):
    """One-line text entry. Dismisses with the string, or None on escape."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, value: str = "", placeholder: str = "", hint: str = "") -> None:
        super().__init__()
        self._title = title
        self._value = value
        self._placeholder = placeholder
        self._hint = hint or "enter accepts · esc cancels"

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            yield Input(value=self._value, placeholder=self._placeholder, id="entry")
            yield Label(self._hint, classes="dialog-hint")

    def on_mount(self) -> None:
        self.query_one("#entry", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_cancel(self) -> None:
        self.dismiss(None)


class Confirm(ModalScreen[bool]):
    """Yes/no gate in front of anything that changes state."""

    BINDINGS = [Binding("escape", "no", "Cancel")]

    def __init__(self, title: str, body: str, confirm_label: str = "Do it") -> None:
        super().__init__()
        self._title = title
        self._body = body
        self._confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            yield Static(self._body)
            with Horizontal(classes="dialog-hint"):
                yield Button(self._confirm_label, variant="warning", id="yes")
                yield Button("Cancel", variant="default", id="no")

    def on_mount(self) -> None:
        self.query_one("#yes", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_no(self) -> None:
        self.dismiss(False)


class Viewer(ModalScreen[None]):
    """Scrollable read-only pane, optionally syntax highlighted."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    def __init__(self, title: str, body: str, lexer: str | None = None) -> None:
        super().__init__()
        self._title = title
        self._body = body or "(empty)"
        self._lexer = lexer

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog-wide"):
            yield Label(self._title, classes="dialog-title")
            with VerticalScroll(classes="viewer"):
                if self._lexer:
                    yield Static(
                        Syntax(self._body, self._lexer, theme="ansi_dark", word_wrap=True)
                    )
                else:
                    yield Static(Text(self._body))
            yield Label("esc closes", classes="dialog-hint")

    def action_close(self) -> None:
        self.dismiss(None)
