FROM node:20-bookworm-slim

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
