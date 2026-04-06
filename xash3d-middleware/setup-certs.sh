#!/bin/bash
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -days 14 -nodes -keyout cert.key -out cert.crt -subj "/CN=localhost"
openssl pkcs12 -export -passout pass: -in cert.crt -inkey cert.key -out cert.p12
openssl x509 -in cert.crt -outform der | openssl dgst -sha256 -binary | openssl base64
