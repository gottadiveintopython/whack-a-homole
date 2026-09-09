# zipappに必要なファイル。 main.py を __main__.py に改名すれば良いだけにも思えるが
# buildozerは main.py を求めるのでそれはできない。なので両対応したければ両方のファイルが要る。

from main import WhackahomoleApp
WhackahomoleApp(title="Whack-A-Homole").run()
