import asyncio
import abc
from typing import Tuple


class BaseListener(abc.ABC):
    """Abstract base class for all listeners in the Mutt system.
    
    Listeners are responsible for receiving data from various sources,
    parsing it, and pushing parsed messages to a queue for further processing.
    """
    
    def __init__(self, queue: asyncio.Queue):
        """Initialize the listener with a queue for parsed messages.
        
        Args:
            queue: An asyncio.Queue instance where parsed messages will be pushed.
        """
        self.queue = queue
        self._is_running = False
        self._server_task = None
    
    @abc.abstractmethod
    async def start(self) -> None:
        """Start the listening server.
        
        This method should be implemented by subclasses to start listening
        for incoming data from their specific source (TCP, UDP, etc.).
        """
        pass
    
    @abc.abstractmethod
    async def stop(self) -> None:
        """Stop the listening server.
        
        This method should be implemented by subclasses to cleanly stop
        the listener and release any resources.
        """
        pass
    
    @abc.abstractmethod
    def process_data(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Parse incoming data and push parsed messages to the queue.
        
        This method should be implemented by subclasses to handle the
        specific data format they expect to receive.
        
        Args:
            data: Raw bytes received from the client.
            addr: Tuple containing (host, port) of the sender.
        """
        pass
    
    @property
    def is_running(self) -> bool:
        """Check if the listener is currently running.
        
        Returns:
            True if the listener is running, False otherwise.
        """
        return self._is_running
