import aiotest.run
import trollius

config = aiotest.TestConfig()
config.asyncio = trollius
config.new_event_pool_policy = trollius.DefaultEventLoopPolicy
config.call_soon_check_closed = True
aiotest.run.main(config)
