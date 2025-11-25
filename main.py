import sys
import warnings
import os

os.environ["PYTHONWARNINGS"] = "ignore"
warnings.filterwarnings("ignore")
warnings.simplefilter("ignore", ResourceWarning)
warnings.simplefilter("ignore", RuntimeWarning)

if sys.platform == "win32":
    import logging
    import asyncio

    logging.getLogger("asyncio").setLevel(logging.CRITICAL)
    logging.getLogger("playwright").setLevel(logging.ERROR)
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

import asyncio
from datetime import datetime
from typing import List

from config import Config
from models import Listing
from utils.storage import Storage

from parsers.avito import AvitoParser
from parsers.farpost import FarPostParser
from parsers.cian import CianParser

async def run_source(parser_cls, config: Config, max_pages: int) -> List[Listing]:
    async with parser_cls(config) as parser:
        return await parser.parse_all(max_pages=max_pages)

async def main_async(max_pages: int = 3) -> None:
    config = Config.from_env()
    storage = Storage(config.output_dir)

    tasks = []
    for src in config.enabled_sources:
        if src == "avito":
            tasks.append(run_source(AvitoParser, config, max_pages))
        elif src == "farpost":
            tasks.append(run_source(FarPostParser, config, max_pages))
        elif src == "cian":
            tasks.append(run_source(CianParser, config, max_pages))

    results: List[List[Listing]] = await asyncio.gather(*tasks, return_exceptions=False)
    listings: List[Listing] = [item for sub in results for item in sub]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if config.save_json:
        json_path = storage.save_json(listings, f"listings_{ts}.json")
    if config.save_csv:
        csv_path = storage.save_csv(listings, f"listings_{ts}.csv")

def _suppress_del_exceptions():
    import asyncio.proactor_events
    import asyncio.base_subprocess

    try:
        original_del_proactor = asyncio.proactor_events._ProactorBasePipeTransport.__del__
        original_del_subprocess = asyncio.base_subprocess.BaseSubprocessTransport.__del__

        def safe_del_proactor(self):
            try:
                original_del_proactor(self)
            except (ValueError, RuntimeError, AttributeError):
                pass

        def safe_del_subprocess(self):
            try:
                original_del_subprocess(self)
            except (ValueError, RuntimeError, AttributeError):
                pass

        asyncio.proactor_events._ProactorBasePipeTransport.__del__ = safe_del_proactor
        asyncio.base_subprocess.BaseSubprocessTransport.__del__ = safe_del_subprocess
    except Exception:
        pass

def main() -> None:
    if sys.platform == "win32":
        try:
            _suppress_del_exceptions()
        except Exception:
            pass

    try:
        if sys.platform == "win32":
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(main_async(max_pages=3))
            finally:
                try:
                    pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                    if pending:
                        for task in pending:
                            task.cancel()
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
                try:
                    loop.close()
                except Exception:
                    pass
        else:
            asyncio.run(main_async(max_pages=3))
    except KeyboardInterrupt:
        pass
    except Exception:
        pass
    finally:
        import gc
        gc.collect()
        if sys.platform == "win32":
            import time
            time.sleep(0.5)

if __name__ == "__main__":
    main()
