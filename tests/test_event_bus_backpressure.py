import asyncio
from notsip.events import Event,EventBus


def test_event_subscriber_overflow_is_reported():
    async def run():
        bus=EventBus(subscriber_queue_size=2);bus.subscribe()
        await bus.publish(Event('sensor.reading',{'n':1}))
        await bus.publish(Event('sensor.reading',{'n':2}))
        errors=await bus.publish(Event('sensor.reading',{'n':3}))
        return errors
    errors=asyncio.run(run())
    assert any(e['kind']=='subscriber_overflow' for e in errors)
