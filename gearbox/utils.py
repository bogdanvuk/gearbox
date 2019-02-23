from pygears.conf import Inject, inject_async


def single_shot_connect(signal, slot):
    def disconnect():
        signal.disconnect(slot)
        signal.disconnect(disconnect)

    signal.connect(slot)
    signal.connect(disconnect)


def trigger(obj, signal):
    def wrapper(func):
        @inject_async
        def waiter(emitter=Inject(obj)):
            getattr(emitter, signal).connect(func)

        return waiter

    return wrapper
