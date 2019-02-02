from pygears.conf import Inject, inject_async


def trigger(obj, signal):
    def wrapper(func):
        @inject_async
        def waiter(emitter=Inject(obj)):
            getattr(emitter, signal).connect(func)

        return waiter

    return wrapper
