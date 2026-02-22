from kivy.app import App
from kivy.core.window import Window

from game import GameWidget


class GameApp(App):
    """Entry point for the Kivy 2.5D shooter prototype."""

    def build(self):
        Window.size = (1920, 1080)
        Window.clearcolor = (0.08, 0.08, 0.1, 1)
        Window.title = "Kivy 2.5D Shooter - Phase 0"
        return GameWidget()


if __name__ == "__main__":
    GameApp().run()
