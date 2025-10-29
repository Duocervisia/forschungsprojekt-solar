FROM nodered/node-red:latest

# Install dashboard UI during image build so the container starts with it available
USER root
RUN npm install --no-update-notifier --no-audit --unsafe-perm node-red-dashboard
USER node-red
