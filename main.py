import asyncio
import signal
import sys
from typing import Optional

import dtimebot


main_task: Optional[asyncio.Task] = None
async def main():
	global main_task
	loop = asyncio.get_running_loop()
	main_task = asyncio.current_task(loop)
	if sys.platform != "win32":
		for sig in (signal.SIGINT, signal.SIGTERM):
			loop.add_signal_handler(sig, lambda *_: main_task.cancel())

	await dtimebot.start()

	try: await loop.create_future()
	except asyncio.CancelledError: pass

	await dtimebot.stop()

if __name__ == "__main__":
	asyncio.run(main())
