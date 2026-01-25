import inspect
from pipecat.transports.network.fastapi_websocket import FastAPIWebsocketTransport

print("FastAPIWebsocketTransport Init Signature:")
print(inspect.signature(FastAPIWebsocketTransport.__init__))
