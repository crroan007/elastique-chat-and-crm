import inspect
from pipecat.transports.network.fastapi_websocket import FastAPIWebsocketParams

print("FastAPIWebsocketParams Init Signature:")
try:
    print(inspect.signature(FastAPIWebsocketParams.__init__))
except:
    # Might be dataclass
    import dataclasses
    print(dataclasses.fields(FastAPIWebsocketParams))
