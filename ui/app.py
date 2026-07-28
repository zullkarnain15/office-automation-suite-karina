"""Single-window OAS-K Unified UI shell for Sprint UI1."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from config.app_config import APP_VERSION, ASSETS_PATH, PROJECT_ROOT
from shared.database import StartupDatabaseMigrationError
from ui.constants import (
    APP_TITLE,
    DEFAULT_PAGE_ID,
    SIDEBAR_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_WIDTH,
)
from ui.context import AppContext
from ui.dpi import enable_dpi_awareness
from ui.icon_manager import IconManager
from ui.models import PageDefinition, PageLoadError, StatusMetadata
from ui.navigation import NavigationController
from ui.page_registry import PageRegistry, build_default_page_registry
from ui.pages.error_page import ErrorPage
from ui.style_manager import StyleManager
from ui.widgets import Header, Sidebar, StatusBar
from ui.window_state import WindowState

logger = logging.getLogger(__name__)


class OASKUnifiedApp:
    """Lightweight single-window shell with lazy cached pages."""

    def __init__(
        self,
        root: tk.Tk | None = None,
        *,
        context: AppContext | None = None,
        registry: PageRegistry | None = None,
        window_state: WindowState | None = None,
    ) -> None:
        if root is None:
            enable_dpi_awareness()
        self.root = root or tk.Tk()
        self.window_state = window_state or WindowState()
        self.registry = registry or build_default_page_registry()
        self.context = context or self._default_context()
        self._closing = False

        self._configure_window()
        self.style = StyleManager().apply(self.root)
        self._welcome_starting = False
        self.startup_database_result = None
        self._build_welcome_splash()
        if self.context.app_services is None:
            from ui.services.service_container import (
                build_default_app_services,
            )

            self.context.app_services = build_default_app_services(
                self.root,
                application_version=self.context.application_version,
                project_root=self.context.project_root,
            )
        self.icon_manager = IconManager(
            self.context.assets_path / "icons",
            master=self.root,
            logger=self.context.logger,
        )
        self._apply_window_icon()
        self._build_layout()
        self.navigation = NavigationController(
            self.registry,
            self.content,
            self.context,
            self,
            error_factory=self._build_error_page,
            header_callback=self.header.update_metadata,
            status_callback=self.status_bar.update_metadata,
            active_callback=self._set_active_page,
            logger=self.context.logger,
        )
        self.context.navigate = self.navigate
        self.context.set_status = self._set_status_message
        self.sidebar.command = self.navigate
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Configure>", self._capture_window_state, add="+")
        self._welcome_splash.tkraise()
        self._welcome_return_binding = self.root.bind(
            "<Return>",
            self._start_from_welcome,
            add="+",
        )

    def _prepare_startup_database(self):
        prepare = getattr(
            self.context.app_services.storage_service,
            "prepare_startup_database",
            None,
        )
        if not callable(prepare):
            return None

        def progress(message: str) -> None:
            self._welcome_status_var.set(message)
            self.root.update_idletasks()

        result = prepare(progress=progress)
        self._welcome_status_var.set("Menyiapkan aplikasi...")
        return result

    def _start_from_welcome(self, _event: object | None = None) -> None:
        if self._welcome_starting:
            return
        self._welcome_starting = True
        self._welcome_start_button.configure(state="disabled")
        try:
            self.startup_database_result = self._prepare_startup_database()
            self.navigate(DEFAULT_PAGE_ID)
            self._dismiss_welcome_splash()
        except StartupDatabaseMigrationError as exc:
            self.context.logger.exception(
                "Startup database preparation failed."
            )
            messagebox.showerror(
                "Pembaruan Database Gagal",
                (
                    f"{exc}\n\n"
                    "Aplikasi dihentikan untuk melindungi data production."
                ),
                parent=self.root,
            )
            self.root.destroy()

    def _build_welcome_splash(self) -> None:
        self._welcome_status_var = tk.StringVar(
            value="Tekan START atau Enter untuk memulai."
        )
        self._welcome_icon_manager = IconManager(
            self.context.assets_path / "icons" / "png",
            master=self.root,
            logger=self.context.logger,
        )
        self._welcome_image = self._welcome_icon_manager.load(
            "welcome.png",
            size=140,
        )
        self._welcome_start_image = self._welcome_icon_manager.load(
            "start_button_pxl.png",
            size=(200, 80),
        )

        splash = ttk.Frame(self.root, style="OASK.TFrame")
        splash.place(x=0, y=0, relwidth=1, relheight=1)
        splash.columnconfigure(0, weight=1)
        splash.columnconfigure(2, weight=1)
        splash.rowconfigure(0, weight=1)
        splash.rowconfigure(2, weight=1)

        content = ttk.Frame(splash, style="OASK.TFrame")
        content.grid(row=1, column=1)
        if self._welcome_image is not None:
            ttk.Label(
                content,
                image=self._welcome_image,
                style="WelcomeImage.TLabel",
            ).grid(row=0, column=0, rowspan=4, padx=(0, 24))

        text = ttk.Frame(content, style="OASK.TFrame")
        text.grid(row=0, column=1, rowspan=4, sticky="w")
        ttk.Label(
            text,
            text="WELCOME TO",
            style="WelcomeEyebrow.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            text,
            text="OFFICE AUTOMATION SUITE - KARINA",
            style="WelcomeTitle.TLabel",
        ).pack(anchor="w", pady=(5, 4))
        ttk.Label(
            text,
            text="BY HR SERVICES",
            style="WelcomeByline.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            text,
            textvariable=self._welcome_status_var,
            style="WelcomeStatus.TLabel",
        ).pack(anchor="w", pady=(14, 8))
        self._welcome_start_button = ttk.Button(
            text,
            image=self._welcome_start_image,
            command=self._start_from_welcome,
            style="WelcomeStart.TButton",
            cursor="hand2",
            takefocus=True,
        )
        self._welcome_start_button.pack(anchor="w")
        self._welcome_splash = splash
        self.root.update_idletasks()

    def _dismiss_welcome_splash(self) -> None:
        if self._welcome_return_binding:
            self.root.unbind("<Return>", self._welcome_return_binding)
            self._welcome_return_binding = None
        try:
            if self._welcome_splash.winfo_exists():
                self._welcome_splash.destroy()
        except tk.TclError:
            return
        self._welcome_icon_manager.clear()

    @staticmethod
    def _default_context() -> AppContext:
        return AppContext(
            project_root=PROJECT_ROOT,
            assets_path=ASSETS_PATH,
            application_version=APP_VERSION,
            logger=logger,
        )

    def _configure_window(self) -> None:
        self.root.title(APP_TITLE)
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.resizable(True, True)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(1, weight=1)
        self._center_window(WINDOW_WIDTH, WINDOW_HEIGHT)

    def _center_window(self, width: int, height: int) -> None:
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        height = min(height, max(WINDOW_MIN_HEIGHT, screen_height - 80))
        width = min(width, max(WINDOW_MIN_WIDTH, screen_width - 40))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        if screen_height - height <= 100:
            y = 0
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _apply_window_icon(self) -> None:
        path = self.icon_manager.application_icon_path()
        if path is None:
            self.context.logger.warning("Application icon is missing.")
            return
        try:
            self.root.iconbitmap(str(path))
        except (tk.TclError, OSError) as exc:
            self.context.logger.warning(
                "Application icon is unsupported: %s",
                exc,
            )

    def _build_layout(self) -> None:
        self.header_icon_manager = IconManager(
            self.context.assets_path / "icons" / "png",
            master=self.root,
            logger=self.context.logger,
        )
        self.header = Header(self.root, self.header_icon_manager)
        self.header.grid(row=0, column=1, sticky="ew")

        self.content = ttk.Frame(
            self.root,
            style="OASK.TFrame",
        )
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.status_bar = StatusBar(
            self.root,
            self.context.application_version,
        )
        self.status_bar.grid(row=2, column=1, sticky="ew")

        sidebar_container = ttk.Frame(
            self.root,
            width=SIDEBAR_WIDTH,
            style="Sidebar.TFrame",
        )
        sidebar_container.grid(
            row=0,
            column=0,
            rowspan=3,
            sticky="nsew",
        )
        sidebar_container.grid_propagate(False)
        sidebar_container.columnconfigure(0, weight=1)
        sidebar_container.rowconfigure(0, weight=1)
        self.sidebar = Sidebar(
            sidebar_container,
            self.registry,
            self.icon_manager,
            self.navigate,
            application_version=self.context.application_version,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")

    def navigate(self, page_id: str) -> bool:
        return self.navigation.navigate(page_id)

    def show_page(self, page: ttk.Frame) -> None:
        page.grid(row=0, column=0, sticky="nsew")
        page.tkraise()

    @staticmethod
    def hide_page(page: ttk.Frame) -> None:
        page.grid_remove()

    def _build_error_page(
        self,
        definition: PageDefinition,
        error: PageLoadError,
    ) -> ErrorPage:
        return ErrorPage(
            self.content,
            self.context,
            definition,
            error,
        )

    def _set_active_page(self, page_id: str) -> None:
        self.window_state.selected_page = page_id
        self.sidebar.set_active(page_id)

    def _set_status_message(self, message: str) -> None:
        selected_id = self.navigation.active_page_id or DEFAULT_PAGE_ID
        selected = self.registry.get(selected_id)
        self.status_bar.update_metadata(
            StatusMetadata(
                message=message,
                selected_page=selected.title,
            )
        )

    def _capture_window_state(self, event: tk.Event) -> None:
        if event.widget is not self.root:
            return
        try:
            maximized = self.root.state() == "zoomed"
        except tk.TclError:
            maximized = False
        self.window_state.update_geometry(
            self.root.winfo_width(),
            self.root.winfo_height(),
            maximized=maximized,
        )

    def close(self) -> bool:
        if self._closing:
            return False
        if not self.navigation.close():
            self.status_bar.update_metadata(
                StatusMetadata(
                    message="Penutupan dibatalkan",
                    selected_page=self.registry.get(
                        self.navigation.active_page_id or DEFAULT_PAGE_ID
                    ).title,
                )
            )
            return False
        self._closing = True
        if self.context.app_services is not None:
            self.context.app_services.task_runner.shutdown()
        self.icon_manager.clear()
        self.root.destroy()
        return True

    def run(self) -> None:
        self.root.mainloop()


def create_app(
    *,
    project_root: Path = PROJECT_ROOT,
) -> OASKUnifiedApp:
    context = AppContext(
        project_root=project_root,
        assets_path=project_root / "assets",
        application_version=APP_VERSION,
        logger=logger,
    )
    return OASKUnifiedApp(context=context)
