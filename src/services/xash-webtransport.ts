import { type Packet, Xash3D, type Xash3DOptions, Net } from 'xash3d-fwgs';

export interface Xash3DOptionsWT extends Xash3DOptions {
  wtServerUrl?: string;
  wtServerCertificateHashBase64?: string;
  onError?: () => void;
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binaryString = atob(base64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
}

export class Xash3DWebTransport extends Xash3D {
  private transport?: WebTransport;
  private datagramWriter?: WritableStreamDefaultWriter<Uint8Array>;
  private wtServerUrl?: string;
  private certificateHashBase64?: string;
  private onError?: () => void;

  constructor(opts?: Xash3DOptionsWT) {
    super(opts);
    this.wtServerUrl = opts?.wtServerUrl;
    this.certificateHashBase64 = opts?.wtServerCertificateHashBase64;
    this.net = new Net(this);
    this.onError = opts?.onError;
  }

  async init() {
    await Promise.all([super.init(), this.connect()]);
  }

  _onError(errorUrl: string) {
    const keepLoading = confirm(`Failed to connect to ${errorUrl}, continue?`);
    if (!keepLoading) {
      this.onError?.();
      window.location.reload();
    }
  }

  async connect() {
    if (!this.wtServerUrl) return;

    const url = `https://${this.wtServerUrl}/`;
    const options: WebTransportOptions = { 
      requireUnreliable: true
    };

    if (this.certificateHashBase64) {
      options.serverCertificateHashes = [
        {
          algorithm: 'sha-256',
          value: base64ToArrayBuffer(this.certificateHashBase64),
        },
      ];
    }

    console.log("Connecting with:", options)
    try {
      this.transport = new WebTransport(url, options);

      // Wait for the connection to fully establish
      await this.transport.ready;

      // Cache the writer once so we don't incur the overhead of repeatedly 
      // locking and unlocking the writable stream in the hot game loop.
      this.datagramWriter = this.transport.datagrams.writable.getWriter();

      this.startReadingDatagrams();
    } catch (e) {
      console.error('WebTransport connection failed:', e);
      this._onError(url);
    }
  }

  private async startReadingDatagrams() {
    if (!this.transport) return;

    const reader = this.transport.datagrams.readable.getReader();
    try {
      while (true) {
        const { value, done } = await reader.read();
        console.log(value, done)
        if (done) break;

        const packet: Packet = {
          ip: [127, 0, 0, 1],
          port: 8080,
          data: value,
        };

        (this.net as Net).incoming.enqueue(packet);
      }
    } catch (e) {
      console.error('Error reading WebTransport datagrams:', e);
    } finally {
      reader.releaseLock();
    }
  }

  sendto(packet: Packet) {
    if (!this.datagramWriter) return;

    this.datagramWriter.write(new Uint8Array(packet.data)).catch((e) => {
      console.error('Datagram send failed:', e);
    });
  }
}
