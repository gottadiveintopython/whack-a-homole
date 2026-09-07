from contextlib import ExitStack

from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
import asynckivy as ak
from asynckivy import transition

from whack_a_homole import SharedStuff
from whack_a_homole.utils import is_colliding_and_not_wheel


KV = r"""
BoxLayout:
    pos_hint: {"x": 0, "y": 0, }
    orientation: "vertical"
    padding: "20dp"
    Label:
        id: msg
        markup: True
        font_size: "40sp"
        halign: "center"
    Image:
        id: image
"""


async def main(parent: FloatLayout, userdata: SharedStuff, *, _cache=[]):
    with ExitStack() as stack:
        defer = stack.callback

        root = _cache.pop() if _cache else Builder.load_string(KV)
        defer(_cache.append, root)
        parent.add_widget(root)
        defer(parent.remove_widget, root)

        s_data, s_states = userdata
        score = s_states.last_game_score
        if score < 30:
            img_key = "orz"
            msg = "Try Harder"
        elif score < 60:
            img_key = "clap"
            msg = "Awesome"
        else:
            img_key = "robot"
            msg = "You must have cheated!"
        root.ids.image.texture = s_data.images[img_key]
        root.ids.msg.text = f"[color=#8470ff]{score}pts[/color]\n{msg}"

        yield

        await ak.event(root, "on_touch_down", filter=is_colliding_and_not_wheel, stop_dispatching=True)

        yield "whack_a_homole.scenes.title.main", transition.fade
