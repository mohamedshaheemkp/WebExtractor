import asyncio

from webextractor.downloaders.retry import RetryHandler


counter = 0


async def unstable():

    global counter

    counter += 1

    if counter < 3:
        raise RuntimeError("Retry")

    return "Success"


async def main():

    retry = RetryHandler()

    result = await retry.run(unstable)

    print(result)


asyncio.run(main())