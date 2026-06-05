"""Thread lifecycle management for background scraping."""

import threading
import queue
import asyncio
import logging
import uuid
from typing import Optional, List, Dict

from queue_protocol import Message

logger = logging.getLogger(__name__)


class ScraperWorker:
    """Manages background scraper thread lifecycle and message queue."""

    def __init__(self):
        """Initialize worker with empty queue and no thread."""
        self.message_queue: queue.Queue = queue.Queue(maxsize=1000)
        self.thread: Optional[threading.Thread] = None
        self.worker_id = str(uuid.uuid4())[:8]
        self._stop_event = threading.Event()

    def spawn(
        self,
        urls: List[str],
        env: Optional[Dict[str, str]] = None,
        window_controller=None,
        anomaly_detector=None,
    ) -> None:
        """
        Spawn background thread to scrape profiles.

        Args:
            urls: List of LinkedIn profile URLs to scrape.
            env: OS environment dict for Chromium execution.
            window_controller: ExecutionWindowController instance.
            anomaly_detector: AnomalyDetector instance.
        """
        if self.thread and self.thread.is_alive():
            logger.warning("Worker already running; ignoring spawn request")
            return

        self.message_queue = queue.Queue(maxsize=1000)
        self._stop_event.clear()

        # Import here to avoid circular dependency
        from scraper import scrape_profile_batch, ExecutionWindowController, AnomalyDetector

        # Use provided controllers or create new ones
        if window_controller is None:
            window_controller = ExecutionWindowController()
        if anomaly_detector is None:
            anomaly_detector = AnomalyDetector()

        # Create thread with target function
        self.thread = threading.Thread(
            target=self._run_batch,
            args=(urls, env, window_controller, anomaly_detector),
            daemon=True,
        )
        self.thread.start()
        logger.info(f"Worker {self.worker_id} spawned with {len(urls)} URLs")

    def _run_batch(
        self,
        urls: List[str],
        env: Optional[Dict[str, str]],
        window_controller,
        anomaly_detector,
    ) -> None:
        """
        Run scraping batch in background thread.

        Wraps asyncio event loop and calls scrape_profile_batch.
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            from scraper import scrape_profile_batch

            loop.run_until_complete(
                scrape_profile_batch(
                    urls=urls,
                    message_queue=self.message_queue,
                    window_controller=window_controller,
                    anomaly_detector=anomaly_detector,
                    env=env,
                    worker_id=self.worker_id,
                    stop_event=self._stop_event,
                )
            )
        except Exception as e:
            logger.error(f"Worker {self.worker_id} encountered error: {e}", exc_info=True)
        finally:
            loop.close()
            logger.info(f"Worker {self.worker_id} completed")

    def get_next_message(self, timeout: float = 0.1) -> Optional[Message]:
        """
        Non-blocking get of next message from queue.

        Args:
            timeout: Timeout in seconds for queue.get.

        Returns:
            Message if available, None otherwise.
        """
        try:
            return self.message_queue.get(block=False)
        except queue.Empty:
            return None

    def is_alive(self) -> bool:
        """Check if worker thread is running."""
        return self.thread is not None and self.thread.is_alive()

    def join(self, timeout: float = 30.0) -> bool:
        """
        Wait for worker thread to complete.

        Args:
            timeout: Max seconds to wait.

        Returns:
            True if thread exited cleanly, False if timeout.
        """
        if not self.thread:
            return True

        self.thread.join(timeout=timeout)
        return not self.thread.is_alive()

    def terminate(self) -> None:
        """
        Signal worker to stop and wait for cleanup.

        Uses stop_event for graceful shutdown; forces thread.join timeout.
        """
        logger.info(f"Terminating worker {self.worker_id}")
        self._stop_event.set()
        self.join(timeout=5.0)

        if self.is_alive():
            logger.warning(f"Worker {self.worker_id} did not exit within timeout; may have orphaned process")
