import asyncio

from reaper_loop import reaper_loop_run


async def exception_test() -> None:
    print("THROWING EXCEPTION", flush=True)
    raise Exception("foobar")


async def amain() -> None:
    asyncio.create_task(exception_test())
    await asyncio.sleep(1)
    print("THROWING EXCEPTION IN MAIN", flush=True)
    raise Exception("foo")


def main() -> None:
    reaper_loop_run(amain())


if __name__ == "__main__":
    main()
