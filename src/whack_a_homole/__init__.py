__all__ = ("SharedObjects", "run", )

from typing import TypeAlias
from functools import partial
from contextlib import closing
from dataclasses import dataclass
from io import BytesIO
import pathlib
import sqlite3
from importlib import resources

from kivy.graphics.texture import Texture
from kivy.core.audio_output import SoundLoader, Sound
from kivy.core.image import Image as CoreImage


@dataclass(kw_only=True)
class AppState:
    displays_hit_boxes: bool = False
    game_duration: float = 30.0
    last_game_score: int = -1


SharedObjects: TypeAlias = tuple[dict[str, Texture], dict[str, Sound], AppState]
'''
This is shared across scenes, and is passed to each scene as the ``userdata`` argument.
'''


async def run(parent):
    from asynckivy import transition
    from . import sceneswitcher

    images, sounds = load_assets()
    await sceneswitcher.run(
        "whack_a_homole.scenes.title.main",
        transition.fade,
        parent=parent,
        userdata=(images, sounds, AppState()),
    )


def _reload_texture(image_data: bytes, texture):
    # TODO: This function is untested because I don't know how to trigger an OpenGL context loss.
    # https://kivy.org/doc/master/api-kivy.graphics.texture.html#reloading-the-texture
    img = CoreImage(BytesIO(image_data), ext="png")
    texture.blit_data(img._image._data[0])


def _load_images(cur: sqlite3.Cursor) -> dict[str, Texture]:
    return {
        name: (
            tex := CoreImage(BytesIO(image_data), ext="png").texture,
            tex.add_reload_observer(partial(_reload_texture, image_data)),
        ) and tex
        for name, image_data in cur.execute("SELECT name, image_data FROM Images")
    }


def _load_sounds(cur: sqlite3.Cursor) -> dict[str, Sound]:
    import tempfile
    # SoundLoader does not support loading from memory yet,
    # so we first write to a temporary file, then load it.
    # https://github.com/kivy/kivy/pull/8799

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = pathlib.Path(tmpdir)
        return {
            name: (
                tmp := tmpdir / (name + ".wav"),
                tmp.write_bytes(sound_data),
            ) and SoundLoader.load(str(tmp))
            for name, sound_data in cur.execute("SELECT name, sound_data FROM Sounds")
        }


def load_assets() -> tuple[dict[str, Texture], dict[str, Sound]]:
    # I might try to convert the app to a zipapp in the future,
    # so I use 'importlib.resources' instead of filesystem APIs.
    with sqlite3.connect(":memory:") as conn:
        conn.deserialize(resources.read_binary("whack_a_homole", "assets.sqlite3"))
        with closing(conn.cursor()) as cur:
            return _load_images(cur), _load_sounds(cur)
