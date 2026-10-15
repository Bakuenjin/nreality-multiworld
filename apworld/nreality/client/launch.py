import asyncio
import os
import threading
import webbrowser
from collections.abc import Sequence
from pathlib import Path

import colorama

from CommonClient import get_base_parser, handle_url_arg, logger, server_loop
from Utils import gui_enabled, user_path


def game_files(game_dir: str | None):
    """The player's own build in the MultiworldGG user folder, or a fixed folder for development."""
    from . import bridge
    from .gamefiles import GameFiles, bundled_bootstrap

    folder = game_dir or os.environ.get("NREALITY_GAME_DIR")
    if not folder:
        return GameFiles(user_path("nreality"), bundled_bootstrap())
    folder = Path(folder)
    for swf in (folder / "n_multiworld.swf", folder / "mod" / "n_multiworld.swf"):
        if swf.is_file() and (folder / "ruffle" / "ruffle.js").is_file():
            return bridge.StaticFiles(swf, folder / "ruffle")
    raise FileNotFoundError(f"n_multiworld.swf and ruffle/ruffle.js not found in {folder}")


def prepare(files) -> None:
    try:
        files.prepare()
    except Exception as error:
        logger.error(f"Could not prepare the game: {error}")


async def main(args) -> None:
    from . import bridge
    from .context import MultiworldBackend, NRealityContext

    files = game_files(args.game_dir)
    ctx = NRealityContext(args.connect, args.password, args.port)
    ctx.auth = args.name
    http = bridge.serve(MultiworldBackend(ctx), args.port, files)
    if hasattr(files, "prepare"):
        threading.Thread(target=prepare, args=(files,), name="NReality setup", daemon=True).start()
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
    if gui_enabled:
        ctx.run_gui()
    ctx.run_cli()
    logger.info(f"Game page: {ctx.game_url}")
    if not args.no_browser:
        webbrowser.open(ctx.game_url)
    await ctx.exit_event.wait()
    http.shutdown()
    await ctx.shutdown()


def launch_client(*args: Sequence[str]) -> None:
    parser = get_base_parser(description="NReality client: connects the browser game to MultiworldGG.")
    parser.add_argument("--name", default=None, help="Slot name to connect as.")
    parser.add_argument("--port", type=int, default=8766, help="Local port of the game page.")
    parser.add_argument("--game-dir", default=None, help="Use a fixed folder with n_multiworld.swf and ruffle/.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the game page automatically.")
    parser.add_argument("url", nargs="?", help="MultiworldGG connection url")
    args = handle_url_arg(parser.parse_args(args), parser)
    colorama.just_fix_windows_console()
    asyncio.run(main(args))
    colorama.deinit()
