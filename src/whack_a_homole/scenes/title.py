from contextlib import ExitStack

from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
import asynckivy as ak
from asynckivy import transition

from whack_a_homole import SharedObjects
import whack_a_homole.uix


KV = r"""
BoxLayout:
    pos_hint: {"x": 0, "y": 0, }
    orientation: "vertical"
    padding: "80dp"
    Label:
        text: "Whack-A-Homole"
        font_size: "80sp"
        pos_hint: {"center_x": .5, }
        size_hint_y: 2
    OutlinedButton:
        id: start_button
        text: "Start"
        font_size: "60sp"
        size_hint_x: .5
        pos_hint: {"center_x": .5, }
"""


async def main(parent: FloatLayout, userdata: SharedObjects, *, _cache=[]):
    with ExitStack() as stack:
        defer = stack.callback

        tree = _cache.pop() if _cache else Builder.load_string(KV)
        defer(_cache.append, tree)
        parent.add_widget(tree)
        defer(parent.remove_widget, tree)

        yield

        await ak.event(tree.ids.start_button, "on_release")

        yield "whack_a_homole.scenes.menu.main", transition.fade
