from kivy.app import App
from kivy.config import Config

Config.set('kivy', 'exit_on_escape', '0')

from kivy.core.window import Window
from kivy.uix.widget import Widget

from game import GameWidget


class GameApp(App):
    """Entry point for the Kivy 2.5D shooter prototype."""

    def build(self):
        Window.size = (1920, 1080)
        Window.clearcolor = (0.08, 0.08, 0.1, 1)
        Window.title = "Kivy 2.5D Shooter - Phase 0"
        self.root_container = Widget()
        self.root_container.bind(size=self._sync_game_widget_rect, pos=self._sync_game_widget_rect)
        self.game_widget = None
        self.start_new_game("LOADING")
        return self.root_container

    def _sync_game_widget_rect(self, *args):
        if self.game_widget is None:
            return
        self.game_widget.size = self.root_container.size
        self.game_widget.pos = self.root_container.pos

    def start_new_game(self, initial_state: str = "LOADING"):
        if self.game_widget is not None:
            if hasattr(self.game_widget, "cleanup"):
                self.game_widget.cleanup()
            if self.game_widget.parent is self.root_container:
                self.root_container.remove_widget(self.game_widget)

        self.game_widget = GameWidget(initial_state=initial_state)
        self._sync_game_widget_rect()
        self.root_container.add_widget(self.game_widget)

    def return_to_main_menu(self):
        self.start_new_game("MAIN_MENU")

    def retry_run(self):
        self.start_new_game("PLAYING")


if __name__ == "__main__":
    GameApp().run()
