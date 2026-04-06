import asyncio
import logging
from typing import Dict, Optional

from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.asyncio.server import serve
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import DatagramReceived, HeadersReceived, H3Event
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent

from bridge import WebTransportUdpBridge

# The interface and port where the WebTransport (HTTP/3) server will listen.
WT_SERVER_HOST = "localhost"
WT_SERVER_PORT = 4433

# The destination UDP server where WebTransport datagrams will be forwarded.
# Change this
UDP_TARGET_HOST = "1.2.3.4"
UDP_TARGET_PORT = 27015

CERT_FILE = "cert.crt"
KEY_FILE = "cert.key"

class WebTransportSession:
    def __init__(self, session_id: int, h3_conn: H3Connection, transmit_cb):
        self.session_id = session_id
        self.h3_conn = h3_conn
        self._transmit = transmit_cb
        self.datagram_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=2048)

    async def receive_datagram(self) -> bytes:
        return await self.datagram_queue.get()

    def send_datagram(self, data: bytes):
        self.h3_conn.send_datagram(stream_id=self.session_id, data=data)
        # QuicConnectionProtocol requires an explicit flush to the network 
        # after queuing outgoing data in the H3Connection.
        self._transmit()

class Http3WebTransportProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._http: Optional[H3Connection] = None
        self._wt_sessions: Dict[int, WebTransportSession] = {}

    def quic_event_received(self, event: QuicEvent) -> None:
        if self._http is None:
            self._http = H3Connection(self._quic, enable_webtransport=True)

        for h3_event in self._http.handle_event(event):
            self._h3_event_received(h3_event)

    def _h3_event_received(self, event: H3Event) -> None:
        if isinstance(event, HeadersReceived):
            headers = dict(event.headers)
            
            if (
                headers.get(b":method") == b"CONNECT" and
                headers.get(b":protocol") == b"webtransport"
            ):
                self._handle_wt_connect(event.stream_id)

        elif isinstance(event, DatagramReceived):
            session = self._wt_sessions.get(event.stream_id)
            if session:
                try:
                    session.datagram_queue.put_nowait(event.data)
                except asyncio.QueueFull:
                    logging.warning("Client to WT queue full, dropping datagram")

    def _handle_wt_connect(self, stream_id: int) -> None:
        self._http.send_headers(
            stream_id=stream_id,
            headers=[
                (b":status", b"200"),
            ],
        )
        
        session = WebTransportSession(
            session_id=stream_id,
            h3_conn=self._http,
            transmit_cb=self.transmit
        )
        self._wt_sessions[stream_id] = session

        bridge = WebTransportUdpBridge(
            wt_session=session,
            target_host=UDP_TARGET_HOST,
            target_port=UDP_TARGET_PORT
        )
        
        asyncio.create_task(bridge.start_bridge())

async def main():
    logging.basicConfig(level=logging.INFO)
    
    configuration = QuicConfiguration(
        alpn_protocols=H3_ALPN,
        is_client=False,
        max_datagram_frame_size=65536
    )
    
    configuration.load_cert_chain(CERT_FILE, KEY_FILE)

    await serve(
        host=WT_SERVER_HOST,
        port=WT_SERVER_PORT,
        configuration=configuration,
        create_protocol=Http3WebTransportProtocol
    )
    logging.info(f"WebTransport server listening on UDP {WT_SERVER_HOST}:{WT_SERVER_PORT}")
    logging.info(f"Bridging datagrams to target UDP {UDP_TARGET_HOST}:{UDP_TARGET_PORT}")
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
