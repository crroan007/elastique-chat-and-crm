import pipecat
try:
    from pipecat.services.base import LLMService, TTSService
    print("SUCCESS: Found services in base")
except ImportError:
    print("FAILED: loading from base")
    import pipecat.services
    print("Available in pipecat.services:", dir(pipecat.services))
