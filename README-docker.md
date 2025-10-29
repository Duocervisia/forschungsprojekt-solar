# MQTT + Node-RED local development using Docker Compose

This repository includes a small Docker Compose setup to run an MQTT broker (Eclipse Mosquitto)
and Node-RED for local development and testing.

Files added:
- `docker-compose.yml` - defines services for Mosquitto and Node-RED
- `mosquitto/config/mosquitto.conf` - minimal Mosquitto configuration (anonymous allowed, for dev only)

Start services:

```powershell
cd <repo-root>
docker compose up -d
```

Open Node-RED UI in your browser:

http://localhost:1880

Connect to MQTT broker from local devices or Node-RED at:

broker: tcp://<host-ip>:1883

Notes / security:
- The Mosquitto config here allows anonymous access for convenience during development. Do NOT use this configuration in production.
- To secure Mosquitto, add password files, TLS certs, or enable authentication and network-level restrictions.
