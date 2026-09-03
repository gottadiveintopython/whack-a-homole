from os import environ
environ.setdefault("KIVY_DESKTOP_PATH_ID", "Whack-A-Homole")
# I remove GstPlayer from the list for a reason.
# See the comments in `_load_sounds` for details.
environ.setdefault("KIVY_AUDIO_OUTPUT", "android,sdl3")

from textwrap import dedent

from kivy.app import App
from kivy.lang import Builder
import asynckivy as ak


class WhackahomoleApp(App):
    def build(self):
        from kivy.uix.floatlayout import FloatLayout
        return FloatLayout()

    def on_start(self):
        import whack_a_homole
        ak.managed_start(add_a_confirmation_step_before_quitting_the_app())
        ak.managed_start(whack_a_homole.run(self.root))


async def add_a_confirmation_step_before_quitting_the_app(*, window=None):
    if window is None:
        from kivy.core.window import Window
        window = Window

    label = Builder.load_string(dedent("""
        Label:
            text: "Press again to quit the app"
            font_size: "24sp"
            padding: [dp(16), dp(8)]
            size_hint: None, None
            size: self.texture_size
            pos_hint: {"center_x": .5, "y": 0.08}
            canvas.before:
                Color:
                    rgb: 0.2, 0.2, 0.2
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
        """))
    try:
        label.opacity = 0.
        while True:
            await ak.event(window, "on_request_close", stop_dispatching=True)
            window.add_widget(label)
            await ak.anim_attrs(label, opacity=1, duration=.2)
            await ak.sleep(1)
            await ak.anim_attrs(label, opacity=0, duration=.2)
            window.remove_widget(label)
    finally:
        window.remove_widget(label)


if __name__ == "__main__":
    WhackahomoleApp().run()
