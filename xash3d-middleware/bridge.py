import asyncio
import logging

class WebTransportUdpBridge:
    def __init__(self, wt_session, target_host: str, target_port: int):
        self.wt_session = wt_session
        self.target_host = target_host
        self.target_port = target_port
        self.udp_transport = None
        self.udp_queue = asyncio.Queue(maxsize=2048)

    async def start_bridge(self):
        loop = asyncio.get_running_loop()

        class UdpReceiverProtocol(asyncio.DatagramProtocol):
            def __init__(self, queue: asyncio.Queue):
                self.queue = queue

            def datagram_received(self, data, addr):
                # asyncio.DatagramProtocol relies on synchronous callbacks. 
                # We use put_nowait to bridge the sync callback into our async 
                # WebTransport transmission loop without blocking the event loop.
                try:
                    self.queue.put_nowait(data)
                except asyncio.QueueFull:
                    logging.warning("UDP to WT queue full, dropping datagram")

        self.udp_transport, _ = await loop.create_datagram_endpoint(
            lambda: UdpReceiverProtocol(self.udp_queue),
            remote_addr=(self.target_host, self.target_port)
        )

        try:
            await asyncio.gather(
                self._forward_wt_to_udp(),
                self._forward_udp_to_wt()
            )
        finally:
            self.udp_transport.close()

    async def _forward_wt_to_udp(self):
        try:
            while True:
                data = await self.wt_session.receive_datagram()
                # print(f"> {data}")
                self.udp_transport.sendto(data)
        except Exception as e:
            logging.error(f"WT to UDP forwarding failed: {e}")

    async def _forward_udp_to_wt(self):
        try:
            while True:
                data = await self.udp_queue.get()
                # print(f"< {data}")
                self.wt_session.send_datagram(data)
        except Exception as e:
            logging.error(f"UDP to WT forwarding failed: {e}")
